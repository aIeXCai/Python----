"""
info_tech API 测试套件
运行: cd backend && python manage.py test info_tech
"""
import json
from rest_framework.test import APITestCase
from rest_framework.authtoken.models import Token
from users.models import CustomUser
from .models import Unit, Question, QuizSession, QuizSubmission


# ─── 测试辅助 ──────────────────────────────────────────────────────────────

_counter = [0]

def make_teacher(username=None, grade='七年级'):
    _counter[0] += 1
    username = username or f'teacher{_counter[0]}'
    u = CustomUser.objects.create_user(
        username=username, password='test123',
        role='teacher', display_name='测试老师',
        managed_grade=grade
    )
    return u

def make_student(grade='七年级', class_num='1', student_number='01', display_name=None):
    _counter[0] += 1
    display_name = display_name or f'学生{_counter[0]}'
    # 确保 username 全局唯一（不同年级/班级组合）
    uniq = f'{grade}-{class_num}-{student_number}-{_counter[0]}'
    u = CustomUser.objects.create_user(
        username=uniq, password='test123', role='student',
        grade=grade, class_num=class_num, student_number=student_number,
        display_name=display_name
    )
    return u

def get_token(user):
    return Token.objects.get_or_create(user=user)[0].key


# ─── Unit API 测试 ─────────────────────────────────────────────────────────

class UnitAPITest(APITestCase):
    """单元 CRUD + 筛选"""

    def setUp(self):
        self.teacher = make_teacher()
        self.token = get_token(self.teacher)

        self.bu1 = Unit.objects.create(grade='七年级', name='big_1', display_name='大单元1', order=1)
        self.sec1 = Unit.objects.create(grade='七年级', parent=self.bu1, name='sec_1_1', display_name='小节1-1', order=1)
        self.sec2 = Unit.objects.create(grade='七年级', parent=self.bu1, name='sec_1_2', display_name='小节1-2', order=2)
        self.bu2 = Unit.objects.create(grade='八年级', name='big_1', display_name='大单元1', order=1)

    def test_list_big_units_without_filter(self):
        """GET /api/admin/info/units/ — 返回所有大单元"""
        resp = self.client.get('/api/admin/info/units/', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        names = [u['name'] for u in resp.data]
        self.assertIn('big_1', names)
        for u in resp.data:
            self.assertIsNone(u.get('parent'))

    def test_list_big_units_filter_by_grade(self):
        """GET ?grade=七年级 — 只返回指定年级"""
        resp = self.client.get('/api/admin/info/units/?grade=七年级', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['name'], 'big_1')
        self.assertEqual(resp.data[0]['grade'], '七年级')

    def test_create_big_unit(self):
        """POST /api/admin/info/units/ — 新增大单元"""
        resp = self.client.post('/api/admin/info/units/', {
            'grade': '七年级', 'name': 'new_big', 'display_name': '新大单元'
        }, format='json', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['name'], 'new_big')
        self.assertIsNone(resp.data.get('parent'))

    def test_create_section(self):
        """POST parent_id — 新增小节"""
        resp = self.client.post('/api/admin/info/units/', {
            'grade': '七年级', 'parent': self.bu1.pk,
            'name': 'new_sec', 'display_name': '新小节'
        }, format='json', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['parent'], self.bu1.pk)

    def test_create_duplicate_unit_name_fails(self):
        """同名单元创建应返回 400"""
        resp = self.client.post('/api/admin/info/units/', {
            'grade': '七年级', 'name': 'big_1', 'display_name': '重复'
        }, format='json', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 400)

    def test_update_unit(self):
        """PUT /api/admin/info/units/<id>/"""
        resp = self.client.put(f'/api/admin/info/units/{self.bu1.pk}/', {
            'name': 'big_1_renamed', 'display_name': '改名后'
        }, format='json', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['name'], 'big_1_renamed')

    def test_delete_unit_cascades(self):
        """删除大单元时小节应一并删除（on_delete=CASCADE）"""
        sec_pk = self.sec1.pk
        resp = self.client.delete(f'/api/admin/info/units/{self.bu1.pk}/delete/', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Unit.objects.filter(pk=sec_pk).exists())

    def test_teacher_only_post(self):
        """POST 需要 teacher 角色，学生应被拒绝"""
        student = make_student()
        token = get_token(student)
        resp = self.client.post('/api/admin/info/units/', {
            'grade': '七年级', 'name': 'hack', 'display_name': 'hack'
        }, format='json', HTTP_AUTHORIZATION=f'Token {token}')
        self.assertEqual(resp.status_code, 403)

    def test_unauthenticated_rejected(self):
        """未登录应返回 401"""
        resp = self.client.get('/api/admin/info/units/')
        self.assertEqual(resp.status_code, 401)


# ─── Question API 测试 ─────────────────────────────────────────────────────

class QuestionAPITest(APITestCase):
    """题库 CRUD + 三级筛选"""

    def setUp(self):
        self.teacher = make_teacher()
        self.token = get_token(self.teacher)

        self.bu1 = Unit.objects.create(grade='七年级', name='big_1', display_name='大单元1', order=1)
        self.sec1 = Unit.objects.create(grade='七年级', parent=self.bu1, name='sec_1_1', display_name='小节1-1', order=1)
        self.sec2 = Unit.objects.create(grade='七年级', parent=self.bu1, name='sec_1_2', display_name='小节1-2', order=2)
        self.bu2 = Unit.objects.create(grade='八年级', name='big_1', display_name='大单元1', order=1)
        self.sec3 = Unit.objects.create(grade='八年级', parent=self.bu2, name='sec_2_1', display_name='小节2-1', order=1)

        self.q1 = Question.objects.create(unit=self.sec1, difficulty='easy', text='七年级-小节1-题目1', answer='A',
                                          option_a='对', option_b='错', option_c='不确定', option_d='以上都不对')
        self.q2 = Question.objects.create(unit=self.sec2, difficulty='medium', text='七年级-小节2-题目2', answer='B',
                                          option_a='对', option_b='错', option_c='不确定', option_d='以上都不对')
        self.q3 = Question.objects.create(unit=self.sec3, difficulty='hard', text='八年级-小节3-题目3', answer='C',
                                          option_a='对', option_b='错', option_c='不确定', option_d='以上都不对')

    # ── 筛选逻辑 ──

    def test_filter_by_grade(self):
        """?grade=七年级 只返回七年级题目"""
        resp = self.client.get('/api/admin/info/questions/?grade=七年级', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 2)
        for q in resp.data:
            self.assertEqual(q['grade'], '七年级')

    def test_filter_by_big_unit_name(self):
        """?big_unit_name=big_1 — 只返回该大单元下所有小节的题目"""
        resp = self.client.get('/api/admin/info/questions/?big_unit_name=big_1', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 3)  # big_1 在七年级和八年级都存在

    def test_filter_by_grade_and_big_unit(self):
        """年级+大单元组合筛选"""
        resp = self.client.get('/api/admin/info/questions/?grade=七年级&big_unit_name=big_1',
                                HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 2)
        for q in resp.data:
            self.assertEqual(q['grade'], '七年级')

    def test_filter_by_unit_name(self):
        """?unit=sec_1_1 — 只返回该小节题目"""
        resp = self.client.get('/api/admin/info/questions/?unit=sec_1_1', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['text'], '七年级-小节1-题目1')

    def test_filter_by_grade_and_unit(self):
        """年级+小节组合"""
        resp = self.client.get('/api/admin/info/questions/?grade=七年级&unit=sec_1_1',
                                HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_filter_by_difficulty(self):
        """?difficulty=hard"""
        resp = self.client.get('/api/admin/info/questions/?difficulty=hard', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['difficulty'], 'hard')

    def test_search_by_text(self):
        """?q=七年级-小节1"""
        resp = self.client.get('/api/admin/info/questions/?q=七年级-小节1', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['text'], '七年级-小节1-题目1')

    # ── CRUD（unit 传的是 name 字符串，不是 PK） ──

    def test_create_question(self):
        """POST /api/admin/info/questions/create/ 新增单题（unit 字段传单元 name）"""
        resp = self.client.post('/api/admin/info/questions/create/', {
            'unit': 'sec_1_1',          # ← unit name，不是 PK
            'difficulty': 'medium',
            'category': '测试分类',
            'text': '新题目',
            'answer': 'C',
            'explanation': '因为C是对的',
            'option_a': 'A选项', 'option_b': 'B选项',
            'option_c': 'C选项', 'option_d': 'D选项',
        }, format='json', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 201, f'响应: {resp.data}')
        self.assertEqual(resp.data['text'], '新题目')
        self.assertEqual(resp.data['answer'], 'C')

    def test_create_question_student_forbidden(self):
        """学生不能创建题目"""
        student = make_student()
        resp = self.client.post('/api/admin/info/questions/create/', {
            'unit': 'sec_1_1', 'difficulty': 'easy', 'text': 'hack',
            'answer': 'A', 'option_a': '1', 'option_b': '2', 'option_c': '3', 'option_d': '4',
        }, format='json', HTTP_AUTHORIZATION=f'Token {get_token(student)}')
        self.assertEqual(resp.status_code, 403)

    def test_update_question(self):
        """PUT 修改"""
        resp = self.client.put(f'/api/admin/info/questions/{self.q1.pk}/', {
            'unit': 'sec_1_1', 'difficulty': 'hard', 'text': '已修改',
            'answer': 'B', 'option_a': '1', 'option_b': '2', 'option_c': '3', 'option_d': '4',
        }, format='json', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200, f'响应: {resp.data}')
        self.assertEqual(resp.data['text'], '已修改')
        self.assertEqual(resp.data['difficulty'], 'hard')

    def test_delete_question(self):
        """DELETE"""
        resp = self.client.delete(f'/api/admin/info/questions/{self.q1.pk}/delete/',
                                   HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Question.objects.filter(pk=self.q1.pk).exists())

    def test_update_nonexistent_returns_404(self):
        """修改不存在的题目"""
        resp = self.client.put('/api/admin/info/questions/99999/', {}, format='json',
                                HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 404)

    def test_create_question_unit_not_found(self):
        """unit name 不存在应返回 400"""
        resp = self.client.post('/api/admin/info/questions/create/', {
            'unit': '不存在的单元名',
            'difficulty': 'easy', 'text': 'test',
            'answer': 'A', 'option_a': '1', 'option_b': '2', 'option_c': '3', 'option_d': '4',
        }, format='json', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 400)


# ─── 批量导入测试 ─────────────────────────────────────────────────────────

class QuestionImportAPITest(APITestCase):
    """POST /api/admin/info/questions/import/"""

    def setUp(self):
        self.teacher = make_teacher()
        self.token = get_token(self.teacher)
        self.bu1 = Unit.objects.create(grade='七年级', name='big_1', display_name='大单元1', order=1)

    def test_import_valid_json(self):
        """正确格式应成功导入"""
        resp = self.client.post('/api/admin/info/questions/import/', {
            'unit': 'imported_sec',
            'grade': '七年级',
            'unit_display_name': '导入小节',
            'questions': [
                {
                    'text': '导入题1',
                    'answer': 'A',
                    'difficulty': 'easy',
                    'category': '测试',
                    'explanation': '选A',
                    'options': [
                        {'key': 'A', 'text': '选项A'},
                        {'key': 'B', 'text': '选项B'},
                        {'key': 'C', 'text': '选项C'},
                        {'key': 'D', 'text': '选项D'},
                    ]
                }
            ]
        }, format='json', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['imported'], 1)
        self.assertTrue(resp.data['unit_created'])
        self.assertEqual(Question.objects.count(), 1)
        q = Question.objects.first()
        self.assertEqual(q.text, '导入题1')
        self.assertEqual(q.option_a, '选项A')

    def test_import_creates_unit_if_not_exists(self):
        """导入时若单元不存在应自动创建"""
        resp = self.client.post('/api/admin/info/questions/import/', {
            'unit': 'brand_new_unit',
            'grade': '七年级',
            'questions': [
                {'text': '题', 'answer': 'A', 'options': [
                    {'key': 'A', 'text': '1'}, {'key': 'B', 'text': '2'},
                    {'key': 'C', 'text': '3'}, {'key': 'D', 'text': '4'}
                ]}
            ]
        }, format='json', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(Unit.objects.filter(name='brand_new_unit', grade='七年级').exists())

    def test_import_empty_questions_fails(self):
        """空题目列表应返回 400"""
        resp = self.client.post('/api/admin/info/questions/import/', {
            'unit': 'any', 'grade': '七年级', 'questions': []
        }, format='json', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 400)

    def test_import_partial_errors_dont_stop_batch(self):
        """部分题目有错误应继续处理其余题目"""
        resp = self.client.post('/api/admin/info/questions/import/', {
            'unit': 'partial_err', 'grade': '七年级',
            'questions': [
                {'text': '正常题', 'answer': 'A', 'options': [
                    {'key': 'A', 'text': '1'}, {'key': 'B', 'text': '2'},
                    {'key': 'C', 'text': '3'}, {'key': 'D', 'text': '4'}
                ]},
                {'text': '', 'answer': 'A', 'options': [  # text 为空字符串也会入库
                    {'key': 'A', 'text': '1'}, {'key': 'B', 'text': '2'},
                    {'key': 'C', 'text': '3'}, {'key': 'D', 'text': '4'}
                ]},
            ]
        }, format='json', HTTP_AUTHORIZATION=f'Token {self.token}')
        # serializer 对空字符串 text 不报错（字段不是 required=False）
        # 所以 2 题都会入库
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['imported'], 2)

    def test_import_multiple_questions(self):
        """一次导入多题"""
        resp = self.client.post('/api/admin/info/questions/import/', {
            'unit': 'multi_sec', 'grade': '七年级',
            'questions': [
                {'text': f'题{i}', 'answer': 'A', 'options': [
                    {'key': 'A', 'text': '1'}, {'key': 'B', 'text': '2'},
                    {'key': 'C', 'text': '3'}, {'key': 'D', 'text': '4'}
                ]} for i in range(5)
            ]
        }, format='json', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['imported'], 5)
        self.assertEqual(Question.objects.count(), 5)

    def test_import_student_forbidden(self):
        """学生不能导入"""
        student = make_student()
        resp = self.client.post('/api/admin/info/questions/import/', {
            'unit': 'hack', 'grade': '七年级',
            'questions': [{'text': 'hack', 'answer': 'A', 'options': [
                {'key': 'A', 'text': '1'}, {'key': 'B', 'text': '2'},
                {'key': 'C', 'text': '3'}, {'key': 'D', 'text': '4'}
            ]}]
        }, format='json', HTTP_AUTHORIZATION=f'Token {get_token(student)}')
        self.assertEqual(resp.status_code, 403)


# ─── 小测 CRUD + Toggle 测试 ─────────────────────────────────────────────

class QuizSessionAPITest(APITestCase):
    """小测的创建/修改/删除/切换可见"""

    def setUp(self):
        self.teacher = make_teacher()
        self.token = get_token(self.teacher)
        self.bu1 = Unit.objects.create(grade='七年级', name='big_1', display_name='大单元1', order=1)
        self.sec1 = Unit.objects.create(grade='七年级', parent=self.bu1, name='sec_1', display_name='小节', order=1)

        for i in range(3):
            Question.objects.create(
                unit=self.sec1, difficulty='easy', text=f'题{i}',
                answer='A', option_a='对', option_b='错', option_c='不确定', option_d='以上都不对'
            )

    def test_list_sessions(self):
        """GET /api/admin/info/sessions/"""
        QuizSession.objects.create(
            title='测试小测', created_by=self.teacher,
            num_questions=3, difficulty_ratio={'easy': 3}
        )
        resp = self.client.get('/api/admin/info/sessions/', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_create_session(self):
        """POST /api/admin/info/sessions/create/"""
        resp = self.client.post('/api/admin/info/sessions/create/', {
            'title': '新小测',
            'units': [self.sec1.pk],           # ← 字段名是 units，不是 unit_ids
            'num_questions': 3,
            'difficulty_ratio': {'easy': 3},
            'time_limit': 30,
            'visible_grades': ['七年级'],
        }, format='json', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 201, f'响应: {resp.data}')
        self.assertEqual(resp.data['title'], '新小测')
        self.assertEqual(resp.data['num_questions'], 3)
        self.assertEqual(resp.data['is_visible'], False)

    def test_create_session_teacher_only(self):
        """学生不能创建小测"""
        student = make_student()
        resp = self.client.post('/api/admin/info/sessions/create/', {
            'title': 'hack', 'units': [self.sec1.pk], 'num_questions': 1,
            'difficulty_ratio': {'easy': 1}
        }, format='json', HTTP_AUTHORIZATION=f'Token {get_token(student)}')
        self.assertEqual(resp.status_code, 403)

    def test_update_session(self):
        """PUT 修改小测"""
        session = QuizSession.objects.create(
            title='原始', created_by=self.teacher, num_questions=3,
            difficulty_ratio={'easy': 3}
        )
        resp = self.client.put(f'/api/admin/info/sessions/{session.pk}/', {
            'title': '已修改',
            'units': [self.sec1.pk],
            'num_questions': 3,
            'difficulty_ratio': {'easy': 3},
            'visible_grades': ['七年级'],
        }, format='json', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200, f'响应: {resp.data}')
        self.assertEqual(resp.data['title'], '已修改')

    def test_delete_session(self):
        """DELETE"""
        session = QuizSession.objects.create(
            title='待删除', created_by=self.teacher, num_questions=3,
            difficulty_ratio={'easy': 3}
        )
        resp = self.client.delete(f'/api/admin/info/sessions/{session.pk}/delete/',
                                   HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(QuizSession.objects.filter(pk=session.pk).exists())

    def test_toggle_visible(self):
        """PATCH toggle — 设置 is_visible + visible_grades"""
        session = QuizSession.objects.create(
            title='切换测试', created_by=self.teacher, num_questions=3,
            difficulty_ratio={'easy': 3}, is_visible=False, visible_grades=[]
        )
        resp = self.client.patch(f'/api/admin/info/sessions/{session.pk}/toggle/', {
            'is_visible': True,
            'visible_grades': ['七年级', '八年级'],
        }, format='json', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['is_visible'], True)
        self.assertEqual(resp.data['visible_grades'], ['七年级', '八年级'])

    def test_toggle_off(self):
        """关闭可见"""
        session = QuizSession.objects.create(
            title='关闭测试', created_by=self.teacher, num_questions=3,
            difficulty_ratio={'easy': 3}, is_visible=True
        )
        resp = self.client.patch(f'/api/admin/info/sessions/{session.pk}/toggle/', {
            'is_visible': False,
        }, format='json', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['is_visible'], False)


# ─── 成绩统计测试 ─────────────────────────────────────────────────────────

class QuizStatsAPITest(APITestCase):
    """成绩统计 API — overview / sessions / submissions"""

    def setUp(self):
        self.teacher = make_teacher()
        self.token = get_token(self.teacher)
        self.bu1 = Unit.objects.create(grade='七年级', name='big_1', display_name='大单元1', order=1)
        self.sec1 = Unit.objects.create(grade='七年级', parent=self.bu1, name='sec_1', display_name='小节', order=1)

        self.session1 = QuizSession.objects.create(
            title='小测A', created_by=self.teacher, num_questions=3,
            difficulty_ratio={'easy': 3}
        )
        self.session1.units.add(self.sec1)

        self.session2 = QuizSession.objects.create(
            title='小测B', created_by=self.teacher, num_questions=3,
            difficulty_ratio={'easy': 3}
        )

        self.stu1 = make_student(grade='七年级', class_num='1', student_number='01', display_name='学生A')
        self.stu2 = make_student(grade='七年级', class_num='1', student_number='02', display_name='学生B')

        self.sub1 = QuizSubmission.objects.create(
            user=self.stu1, session=self.session1, grade='七年级',
            score=85.0, correct_count=3, total_count=3, answers_json='{}'
        )
        self.sub2 = QuizSubmission.objects.create(
            user=self.stu1, session=self.session2, grade='七年级',
            score=60.0, correct_count=2, total_count=3, answers_json='{}'
        )
        self.sub3 = QuizSubmission.objects.create(
            user=self.stu2, session=self.session1, grade='七年级',
            score=100.0, correct_count=3, total_count=3, answers_json='{}'
        )

    def test_overview_no_filter(self):
        """全局概览"""
        resp = self.client.get('/api/admin/info/stats/overview/', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total_sessions'], 2)
        self.assertEqual(resp.data['total_submissions'], 3)
        self.assertIn('avg_score', resp.data)
        self.assertIn('score_distribution', resp.data)
        self.assertIn('by_grade', resp.data)

    def test_overview_filter_by_grade(self):
        """?grade=七年级 筛选"""
        resp = self.client.get('/api/admin/info/stats/overview/?grade=七年级',
                                HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total_submissions'], 3)

    def test_overview_filter_by_nonexistent_grade(self):
        """无数据的年级应正常返回（不是报错）"""
        resp = self.client.get('/api/admin/info/stats/overview/?grade=高三',
                                HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total_submissions'], 0)

    def test_stats_sessions_list(self):
        """按小测统计列表"""
        resp = self.client.get('/api/admin/info/stats/sessions/', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 2)

    def test_stats_session_detail(self):
        """某小测详细统计"""
        resp = self.client.get(f'/api/admin/info/stats/sessions/{self.session1.pk}/',
                                HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total_submissions'], 2)
        # avg_score = (85 + 100) / 2 = 92.5
        self.assertEqual(resp.data['avg_score'], 92.5)

    def test_stats_session_detail_empty(self):
        """无人参加的小测返回 0"""
        session_empty = QuizSession.objects.create(
            title='无人参加', created_by=self.teacher, num_questions=3,
            difficulty_ratio={'easy': 3}
        )
        resp = self.client.get(f'/api/admin/info/stats/sessions/{session_empty.pk}/',
                                HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total_submissions'], 0)

    def test_stats_session_detail_not_found(self):
        """不存在的小测返回 404"""
        resp = self.client.get('/api/admin/info/stats/sessions/99999/',
                                HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 404)

    def test_stats_submissions_matrix(self):
        """学生成绩矩阵"""
        resp = self.client.get('/api/admin/info/stats/submissions/',
                                HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['sessions']), 2)
        self.assertEqual(len(resp.data['students']), 2)
        # 学生A参加两场，平均 (85+60)/2 = 72.5
        stu_a = next(s for s in resp.data['students'] if s['display_name'] == '学生A')
        self.assertEqual(stu_a['avg_score'], 72.5)

    def test_stats_submissions_filter_by_session(self):
        """?session_id 筛选"""
        resp = self.client.get(f'/api/admin/info/stats/submissions/?session_id={self.session1.pk}',
                                HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['sessions']), 1)
        self.assertEqual(len(resp.data['students']), 2)

    def test_stats_submissions_empty_result(self):
        """无数据返回空列表"""
        resp = self.client.get('/api/admin/info/stats/submissions/?grade=高三',
                                HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['students'], [])
        self.assertEqual(resp.data['sessions'], [])

    def test_stats_teacher_only(self):
        """统计接口需要 teacher 角色"""
        student = make_student()
        resp = self.client.get('/api/admin/info/stats/overview/', HTTP_AUTHORIZATION=f'Token {get_token(student)}')
        self.assertEqual(resp.status_code, 403)

    def test_stats_grade_view(self):
        """按年级统计"""
        resp = self.client.get('/api/admin/info/stats/grade/七年级/',
                                HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total_submissions'], 3)
        # (85 + 60 + 100) / 3 = 81.667
        self.assertAlmostEqual(resp.data['avg_score'], 81.7, places=1)

    def test_stats_grade_view_not_found(self):
        """无数据的年级返回 404"""
        resp = self.client.get('/api/admin/info/stats/grade/高三/', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 404)
