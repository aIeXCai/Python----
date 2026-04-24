"""
info_tech 学生端小测 API 测试（views_student.py）
运行: cd backend && python manage.py test info_tech.tests_student_quiz
"""
import json
from rest_framework.test import APITestCase
from rest_framework.authtoken.models import Token
from users.models import CustomUser
from .models import Unit, Question, QuizSession, QuizSubmission


def make_teacher(grade='七年级'):
    u = CustomUser.objects.create_user(
        username=f'teacher_{grade}_{Unit.objects.count()}',
        password='test123', role='teacher',
        display_name='老师', managed_grade=grade
    )
    return u

def make_student(grade='七年级', class_num='1', student_number='01', display_name=None):
    uniq = f'{grade}{class_num}{student_number}{Unit.objects.count()}'
    u = CustomUser.objects.create_user(
        username=f'stu_{uniq}', password='test123', role='student',
        grade=grade, class_num=class_num, student_number=student_number,
        display_name=display_name or f'学生{uniq}',
        managed_grade=grade
    )
    return u

def get_token(user):
    return Token.objects.get_or_create(user=user)[0].key


# ─── 学生端小测列表 ───────────────────────────────────────────────────────

class StudentQuizListAPITest(APITestCase):
    """GET /api/info/quizzes/ — 学生看到自己年级可见的小测列表"""

    def setUp(self):
        self.teacher = make_teacher(grade='七年级')
        self.bu1 = Unit.objects.create(grade='七年级', name='big_1', display_name='大单元1', order=1)
        self.sec1 = Unit.objects.create(grade='七年级', parent=self.bu1, name='sec_1', display_name='小节', order=1)

        for i in range(3):
            Question.objects.create(
                unit=self.sec1, difficulty='easy', text=f'题{i}',
                answer='A', option_a='对', option_b='错', option_c='不确定', option_d='以上都不对'
            )

        self.student = make_student(grade='七年级', class_num='1', student_number='01')
        self.token = get_token(self.student)

    def _make_session(self, title, is_visible=True, visible_grades=None, created_by=None):
        s = QuizSession.objects.create(
            title=title, created_by=created_by or self.teacher,
            num_questions=3, difficulty_ratio={'easy': 3},
            is_visible=is_visible, visible_grades=visible_grades or []
        )
        s.units.add(self.sec1)
        return s

    def test_list_only_visible_sessions(self):
        """只返回 is_visible=True 的小测"""
        self._make_session('可见小测', is_visible=True)
        self._make_session('不可见小测', is_visible=False)
        resp = self.client.get('/api/info/quizzes/', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        titles = [s['title'] for s in resp.data]
        self.assertIn('可见小测', titles)
        self.assertNotIn('不可见小测', titles)

    def test_grade_filter_visible_grades_empty(self):
        """visible_grades=[] 表示全部年级可见"""
        s = self._make_session('全部可见', visible_grades=[])
        resp = self.client.get('/api/info/quizzes/', HTTP_AUTHORIZATION=f'Token {self.token}')
        titles = [s['title'] for s in resp.data]
        self.assertIn('全部可见', titles)

    def test_grade_filter_matches(self):
        """学生年级在 visible_grades 中时应显示"""
        s = self._make_session('七年级可见', visible_grades=['七年级'])
        resp = self.client.get('/api/info/quizzes/', HTTP_AUTHORIZATION=f'Token {self.token}')
        titles = [s['title'] for s in resp.data]
        self.assertIn('七年级可见', titles)

    def test_grade_filter_mismatch(self):
        """学生年级不在 visible_grades 中时隐藏"""
        s = self._make_session('八年级专用', visible_grades=['八年级'])
        resp = self.client.get('/api/info/quizzes/', HTTP_AUTHORIZATION=f'Token {self.token}')
        titles = [s['title'] for s in resp.data]
        self.assertNotIn('八年级专用', titles)

    def test_shows_submitted_status_and_best_score(self):
        """返回是否已提交和最高分"""
        s = self._make_session('含状态小测')
        QuizSubmission.objects.create(
            user=self.student, session=s, grade='七年级',
            score=80.0, correct_count=2, total_count=3, answers_json='{}'
        )
        resp = self.client.get('/api/info/quizzes/', HTTP_AUTHORIZATION=f'Token {self.token}')
        quiz = next(q for q in resp.data if q['title'] == '含状态小测')
        self.assertTrue(quiz['submitted'])
        self.assertEqual(quiz['best_score'], 80.0)

    def test_multiple_submissions_best_score(self):
        """同一小测多次提交返回最高分"""
        s = self._make_session('多次提交')
        QuizSubmission.objects.create(
            user=self.student, session=s, grade='七年级',
            score=60.0, correct_count=2, total_count=3, answers_json='{}'
        )
        QuizSubmission.objects.create(
            user=self.student, session=s, grade='七年级',
            score=90.0, correct_count=3, total_count=3, answers_json='{}'
        )
        resp = self.client.get('/api/info/quizzes/', HTTP_AUTHORIZATION=f'Token {self.token}')
        quiz = next(q for q in resp.data if q['title'] == '多次提交')
        self.assertEqual(quiz['best_score'], 90.0)

    def test_unauthenticated_rejected(self):
        """未登录返回 401"""
        resp = self.client.get('/api/info/quizzes/')
        self.assertEqual(resp.status_code, 401)


# ─── 学生端小测详情（随机抽题+选项打乱）─────────────────────────────────

class StudentQuizDetailAPITest(APITestCase):
    """GET /api/info/quizzes/<id>/ — 获取随机抽的题目（选项打乱）"""

    def setUp(self):
        self.teacher = make_teacher()
        self.bu1 = Unit.objects.create(grade='七年级', name='big_1', display_name='大单元1', order=1)
        self.sec1 = Unit.objects.create(grade='七年级', parent=self.bu1, name='sec_1', display_name='小节', order=1)

        # 创建多个题目
        for i, diff in enumerate(['easy', 'medium', 'hard', 'easy', 'medium']):
            Question.objects.create(
                unit=self.sec1, difficulty=diff, text=f'题{i}难度{diff}',
                answer='A', option_a='选项A', option_b='选项B',
                option_c='选项C', option_d='选项D'
            )

        self.student = make_student()
        self.token = get_token(self.student)

        self.session = QuizSession.objects.create(
            title='抽题测试', created_by=self.teacher,
            num_questions=3, difficulty_ratio={'easy': 1, 'medium': 1, 'hard': 1},
            is_visible=True, visible_grades=[]
        )
        self.session.units.add(self.sec1)

    def test_get_detail_success(self):
        """获取详情成功"""
        resp = self.client.get(
            f'/api/info/quizzes/{self.session.pk}/',
            HTTP_AUTHORIZATION=f'Token {self.token}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['title'], '抽题测试')
        self.assertEqual(len(resp.data['questions']), 3)

    def test_invisible_session_returns_404(self):
        """不可见小测返回 404"""
        self.session.is_visible = False
        self.session.save()
        resp = self.client.get(
            f'/api/info/quizzes/{self.session.pk}/',
            HTTP_AUTHORIZATION=f'Token {self.token}'
        )
        self.assertEqual(resp.status_code, 404)

    def test_wrong_grade_returns_403(self):
        """年级不在 visible_grades 中返回 403"""
        self.session.visible_grades = ['八年级']
        self.session.save()
        resp = self.client.get(
            f'/api/info/quizzes/{self.session.pk}/',
            HTTP_AUTHORIZATION=f'Token {self.token}'
        )
        self.assertEqual(resp.status_code, 403)

    def test_questions_contain_required_fields(self):
        """返回题目包含所有必要字段"""
        resp = self.client.get(
            f'/api/info/quizzes/{self.session.pk}/',
            HTTP_AUTHORIZATION=f'Token {self.token}'
        )
        q = resp.data['questions'][0]
        self.assertIn('id', q)
        self.assertIn('text', q)
        self.assertIn('options', q)
        self.assertIn('correct_answer', q)  # 打乱后的字母
        self.assertIn('shuffled_order', q)

    def test_options_are_shuffled(self):
        """选项顺序是打乱的（不一定原始 ABCD）"""
        resp = self.client.get(
            f'/api/info/quizzes/{self.session.pk}/',
            HTTP_AUTHORIZATION=f'Token {self.token}'
        )
        for q in resp.data['questions']:
            opt_keys = list(q['options'].keys())
            self.assertEqual(sorted(opt_keys), ['A', 'B', 'C', 'D'])
            # shuffled_order 长度应为 4
            self.assertEqual(len(q['shuffled_order']), 4)

    def test_nonexistent_session_returns_404(self):
        """不存在的小测"""
        resp = self.client.get(
            '/api/info/quizzes/99999/',
            HTTP_AUTHORIZATION=f'Token {self.token}'
        )
        self.assertEqual(resp.status_code, 404)

    def test_question_pool_smaller_than_num_questions(self):
        """题库少于所需题目数时返回全部"""
        # 这个 session 抽 100 题但只有 5 题
        session = QuizSession.objects.create(
            title='题不够', created_by=self.teacher,
            num_questions=100, difficulty_ratio={'easy': 100},
            is_visible=True, visible_grades=[]
        )
        session.units.add(self.sec1)
        resp = self.client.get(
            f'/api/info/quizzes/{session.pk}/',
            HTTP_AUTHORIZATION=f'Token {self.token}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['questions']), 5)  # 只有5题


# ─── 学生端提交小测 ───────────────────────────────────────────────────────

class StudentQuizSubmitAPITest(APITestCase):
    """POST /api/info/quizzes/<id>/submit/"""

    def setUp(self):
        self.teacher = make_teacher()
        self.bu1 = Unit.objects.create(grade='七年级', name='big_1', display_name='大单元1', order=1)
        self.sec1 = Unit.objects.create(grade='七年级', parent=self.bu1, name='sec_1', display_name='小节', order=1)

        self.q1 = Question.objects.create(
            unit=self.sec1, difficulty='easy', text='题1',
            answer='A', option_a='对', option_b='错', option_c='不确定', option_d='以上都不对'
        )
        self.q2 = Question.objects.create(
            unit=self.sec1, difficulty='easy', text='题2',
            answer='B', option_a='对', option_b='错', option_c='不确定', option_d='以上都不对'
        )

        self.student = make_student()
        self.token = get_token(self.student)

        self.session = QuizSession.objects.create(
            title='提交测试', created_by=self.teacher,
            num_questions=2, difficulty_ratio={'easy': 2},
            is_visible=True, visible_grades=[]
        )
        self.session.units.add(self.sec1)

    def test_submit_correct_answers(self):
        resp = self.client.post(
            f'/api/info/quizzes/{self.session.pk}/submit/',
            {
                'answers': {str(self.q1.pk): 'A', str(self.q2.pk): 'B'},
                'shuffled_answers': {},
                'shuffled_orders': {},
            },
            format='json',
            HTTP_AUTHORIZATION=f'Token {self.token}'
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['score'], 100.0)
        self.assertEqual(resp.data['correct_count'], 2)

    def test_submit_wrong_answers(self):
        resp = self.client.post(
            f'/api/info/quizzes/{self.session.pk}/submit/',
            {
                'answers': {str(self.q1.pk): 'A', str(self.q2.pk): 'C'},  # q2错
                'shuffled_answers': {},
                'shuffled_orders': {},
            },
            format='json',
            HTTP_AUTHORIZATION=f'Token {self.token}'
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['correct_count'], 1)

    def test_submit_returns_detail(self):
        resp = self.client.post(
            f'/api/info/quizzes/{self.session.pk}/submit/',
            {
                'answers': {str(self.q1.pk): 'A'},
                'shuffled_answers': {},
                'shuffled_orders': {},
            },
            format='json',
            HTTP_AUTHORIZATION=f'Token {self.token}'
        )
        self.assertEqual(resp.status_code, 201)
        self.assertIn('details', resp.data)
        self.assertGreater(len(resp.data['details']), 0)

    def test_submit_saves_submission_record(self):
        resp = self.client.post(
            f'/api/info/quizzes/{self.session.pk}/submit/',
            {
                'answers': {str(self.q1.pk): 'A', str(self.q2.pk): 'B'},
                'shuffled_answers': {},
                'shuffled_orders': {},
            },
            format='json',
            HTTP_AUTHORIZATION=f'Token {self.token}'
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(QuizSubmission.objects.count(), 1)
        sub = QuizSubmission.objects.first()
        self.assertEqual(sub.user, self.student)
        self.assertEqual(sub.session, self.session)

    def test_submit_multiple_times_updates(self):
        for _ in range(3):
            self.client.post(
                f'/api/info/quizzes/{self.session.pk}/submit/',
                {'answers': {str(self.q1.pk): 'A'}, 'shuffled_answers': {}, 'shuffled_orders': {}},
                format='json', HTTP_AUTHORIZATION=f'Token {self.token}'
            )
        self.assertEqual(QuizSubmission.objects.count(), 3)

    def test_submit_invisible_session_returns_404(self):
        """不可见小测无法提交"""
        self.session.is_visible = False
        self.session.save()
        resp = self.client.post(
            f'/api/info/quizzes/{self.session.pk}/submit/',
            {'answers': {}},
            format='json', HTTP_AUTHORIZATION=f'Token {self.token}'
        )
        self.assertEqual(resp.status_code, 404)

    def test_submit_wrong_grade_returns_403(self):
        """年级不在 visible_grades 中无法提交"""
        self.session.visible_grades = ['八年级']
        self.session.save()
        resp = self.client.post(
            f'/api/info/quizzes/{self.session.pk}/submit/',
            {'answers': {}},
            format='json', HTTP_AUTHORIZATION=f'Token {self.token}'
        )
        self.assertEqual(resp.status_code, 403)


# ─── 学生端成绩查看 ───────────────────────────────────────────────────────

class StudentQuizResultAPITest(APITestCase):
    """GET /api/info/quizzes/<id>/result/"""

    def setUp(self):
        self.teacher = make_teacher()
        self.bu1 = Unit.objects.create(grade='七年级', name='big_1', display_name='大单元1', order=1)
        self.sec1 = Unit.objects.create(grade='七年级', parent=self.bu1, name='sec_1', display_name='小节', order=1)

        self.q1 = Question.objects.create(
            unit=self.sec1, difficulty='easy', text='题1',
            answer='A', explanation='因为A对', option_a='对', option_b='错',
            option_c='不确定', option_d='以上都不对'
        )
        self.q2 = Question.objects.create(
            unit=self.sec1, difficulty='easy', text='题2',
            answer='B', explanation='因为B对', option_a='对', option_b='错',
            option_c='不确定', option_d='以上都不对'
        )

        self.student = make_student()
        self.token = get_token(self.student)

        self.session = QuizSession.objects.create(
            title='查成绩测试', created_by=self.teacher,
            num_questions=2, difficulty_ratio={'easy': 2},
            is_visible=True, visible_grades=[]
        )
        self.session.units.add(self.sec1)

    def test_get_result_success(self):
        """有成绩时返回详情"""
        sub = QuizSubmission.objects.create(
            user=self.student, session=self.session, grade='七年级',
            score=50.0, correct_count=1, total_count=2,
            answers_json=json.dumps({
                'answers': {str(self.q1.pk): 'A', str(self.q2.pk): 'C'},
                'shuffled': {},
                'shuffled_orders': {}
            })
        )
        resp = self.client.get(
            f'/api/info/quizzes/{self.session.pk}/result/',
            HTTP_AUTHORIZATION=f'Token {self.token}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['score'], 50.0)
        self.assertEqual(resp.data['correct_count'], 1)
        self.assertIn('question_results', resp.data)

    def test_get_result_no_submission(self):
        """未提交过返回 404"""
        resp = self.client.get(
            f'/api/info/quizzes/{self.session.pk}/result/',
            HTTP_AUTHORIZATION=f'Token {self.token}'
        )
        self.assertEqual(resp.status_code, 404)
        self.assertIn('暂无成绩', resp.data['error'])

    def test_get_result_returns_latest(self):
        """多次提交返回最新一次"""
        QuizSubmission.objects.create(
            user=self.student, session=self.session, grade='七年级',
            score=50.0, correct_count=1, total_count=2,
            answers_json=json.dumps({'answers': {str(self.q1.pk): 'A'}})
        )
        sub2 = QuizSubmission.objects.create(
            user=self.student, session=self.session, grade='七年级',
            score=100.0, correct_count=2, total_count=2,
            answers_json=json.dumps({'answers': {str(self.q1.pk): 'A', str(self.q2.pk): 'B'}})
        )
        resp = self.client.get(
            f'/api/info/quizzes/{self.session.pk}/result/',
            HTTP_AUTHORIZATION=f'Token {self.token}'
        )
        self.assertEqual(resp.data['score'], 100.0)

    def test_get_result_nonexistent_session(self):
        """不存在的小测"""
        resp = self.client.get(
            '/api/info/quizzes/99999/result/',
            HTTP_AUTHORIZATION=f'Token {self.token}'
        )
        self.assertEqual(resp.status_code, 404)

    def test_get_result_unauthenticated(self):
        """未登录拒绝"""
        resp = self.client.get(f'/api/info/quizzes/{self.session.pk}/result/')
        self.assertEqual(resp.status_code, 401)

    def test_get_result_includes_explanation(self):
        """结果包含题目解析"""
        QuizSubmission.objects.create(
            user=self.student, session=self.session, grade='七年级',
            score=50.0, correct_count=1, total_count=2,
            answers_json=json.dumps({
                'answers': {str(self.q1.pk): 'A', str(self.q2.pk): 'B'},
                'shuffled': {},
                'shuffled_orders': {}
            })
        )
        resp = self.client.get(
            f'/api/info/quizzes/{self.session.pk}/result/',
            HTTP_AUTHORIZATION=f'Token {self.token}'
        )
        self.assertEqual(resp.status_code, 200)
        # 解析应出现在 question_results 里
        explanations = [r.get('explanation') for r in resp.data['question_results']]
        self.assertTrue(any(e for e in explanations if e))

    def test_result_old_format_answers_json(self):
        """兼容旧格式 answers_json（纯 dict，不是 {answers,shuffled,shuffled_orders}）"""
        QuizSubmission.objects.create(
            user=self.student, session=self.session, grade='七年级',
            score=50.0, correct_count=1, total_count=2,
            answers_json=json.dumps({str(self.q1.pk): 'A'})  # 旧格式
        )
        resp = self.client.get(
            f'/api/info/quizzes/{self.session.pk}/result/',
            HTTP_AUTHORIZATION=f'Token {self.token}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('question_results', resp.data)
