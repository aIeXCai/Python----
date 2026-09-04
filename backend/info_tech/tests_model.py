"""
info_tech Model 单元测试
运行: cd backend && python manage.py test info_tech.tests_model
"""
from django.test import TestCase
from info_tech.models import Unit, Question, QuizSession, QuizSubmission
from users.models import CustomUser


class UnitModelTest(TestCase):
    """Unit: 三级结构（年级-大单元-小节）"""

    def test_create_big_unit_no_parent(self):
        """大单元 parent=null"""
        u = Unit.objects.create(
            grade='七年级', name='第一单元', display_name='走进人工智能', order=1
        )
        self.assertIsNone(u.parent)
        self.assertEqual(u.grade, '七年级')
        self.assertEqual(str(u), '七年级 · 走进人工智能')

    def test_create_section_with_parent(self):
        """小节 parent=大单元"""
        big = Unit.objects.create(
            grade='七年级', name='第一单元', display_name='走进人工智能', order=1
        )
        sec = Unit.objects.create(
            grade='七年级', parent=big, name='1-1', display_name='1.1 信息及其特征', order=1
        )
        self.assertEqual(sec.parent, big)
        self.assertIn('1.1', sec.display_name)

    def test_sections_related_name(self):
        """大单元.sections 可访问小节"""
        big = Unit.objects.create(grade='七年级', name='第二单元', display_name='第二单元', order=2)
        sec1 = Unit.objects.create(grade='七年级', parent=big, name='2-1', display_name='2.1', order=1)
        sec2 = Unit.objects.create(grade='七年级', parent=big, name='2-2', display_name='2.2', order=2)
        self.assertEqual(big.sections.count(), 2)
        self.assertIn(sec1, big.sections.all())
        self.assertIn(sec2, big.sections.all())

    def test_ordering_by_grade_and_order(self):
        """默认按 grade → order 排序"""
        Unit.objects.create(grade='八年级', name='A', display_name='A', order=1)
        Unit.objects.create(grade='七年级', name='B', display_name='B', order=1)
        Unit.objects.create(grade='七年级', name='C', display_name='C', order=2)
        units = list(Unit.objects.values_list('display_name', flat=True))
        self.assertEqual(units, ['B', 'C', 'A'])  # 七年级在前，按order

    def test_same_name_different_grade(self):
        """同名单元通过 grade 区分（七年级/八年级各有"第一单元"）"""
        u1 = Unit.objects.create(grade='七年级', name='第一单元', display_name='七年级第一单元', order=1)
        u2 = Unit.objects.create(grade='八年级', name='第一单元', display_name='八年级第一单元', order=1)
        self.assertNotEqual(u1.pk, u2.pk)
        self.assertEqual(Unit.objects.filter(name='第一单元').count(), 2)


class QuestionModelTest(TestCase):
    """Question: 题库"""

    def setUp(self):
        self.unit = Unit.objects.create(
            grade='七年级', name='第一单元', display_name='第一单元', order=1
        )

    def test_create_question(self):
        """基本字段"""
        q = Question.objects.create(
            unit=self.unit, difficulty='easy', category='网络',
            text='计算机网络中物理层的功能是？',
            answer='A', explanation='物理层负责比特传输',
            option_a='传输比特', option_b='路由选择', option_c='会话管理', option_d='应用接口'
        )
        self.assertEqual(q.answer, 'A')
        self.assertEqual(q.difficulty, 'easy')
        self.assertIn('物理层', q.text)

    def test_str_shows_unit_and_text(self):
        """__str__ 包含单元名和题目正文"""
        q = Question.objects.create(
            unit=self.unit, difficulty='medium', text='这是一道很长很长很长很长很长的题目',
            answer='B', option_a='A', option_b='B', option_c='C', option_d='D'
        )
        self.assertIn('第一单元', str(q))
        self.assertIn('这是一道很长', str(q)[:30])  # 截断在30字

    def test_difficulty_choices(self):
        """难度选项约束"""
        for diff in ['easy', 'medium', 'hard']:
            q = Question.objects.create(
                unit=self.unit, difficulty=diff, text='题', answer='A',
                option_a='a', option_b='b', option_c='c', option_d='d'
            )
            self.assertEqual(q.difficulty, diff)

    def test_question_ordering_by_id(self):
        """默认按 id 升序（创建顺序）"""
        q1 = Question.objects.create(unit=self.unit, text='题1', answer='A', option_a='a', option_b='b', option_c='c', option_d='d')
        q2 = Question.objects.create(unit=self.unit, text='题2', answer='A', option_a='a', option_b='b', option_c='c', option_d='d')
        self.assertEqual(list(Question.objects.values_list('text', flat=True)), ['题1', '题2'])


class QuizSessionModelTest(TestCase):
    """QuizSession: 小测配置"""

    def setUp(self):
        self.teacher = CustomUser.objects.create_user(
            username='teacher1', password='test', role='teacher',
            display_name='老师', managed_grade='七年级'
        )
        self.unit = Unit.objects.create(grade='七年级', name='第一单元', display_name='第一单元', order=1)

    def test_create_session_defaults(self):
        """默认值：is_visible=False，年级和班级范围均为全部"""
        qs = QuizSession.objects.create(
            title='小测1', created_by=self.teacher,
            num_questions=10, difficulty_ratio={'easy': 10}
        )
        self.assertFalse(qs.is_visible)
        self.assertEqual(qs.visible_grades, [])
        self.assertEqual(qs.visible_classes, [])
        self.assertEqual(str(qs), '小测1')

    def test_session_with_units(self):
        """units 多对多关联"""
        u1 = Unit.objects.create(grade='七年级', name='单元1', display_name='单元1', order=1)
        u2 = Unit.objects.create(grade='七年级', name='单元2', display_name='单元2', order=2)
        qs = QuizSession.objects.create(
            title='多单元小测', created_by=self.teacher,
            num_questions=5, difficulty_ratio={}
        )
        qs.units.set([u1, u2])
        self.assertEqual(qs.units.count(), 2)

    def test_difficulty_ratio_json(self):
        """difficulty_ratio 存 JSON"""
        ratio = {'easy': 7, 'medium': 2, 'hard': 1}
        qs = QuizSession.objects.create(
            title='比例测试', created_by=self.teacher,
            num_questions=10, difficulty_ratio=ratio
        )
        qs.refresh_from_db()
        self.assertEqual(qs.difficulty_ratio['easy'], 7)
        self.assertEqual(qs.difficulty_ratio['hard'], 1)


class QuizSubmissionModelTest(TestCase):
    """QuizSubmission: 学生提交记录"""

    def setUp(self):
        self.teacher = CustomUser.objects.create_user(
            username='teacher1', password='test', role='teacher', display_name='老师'
        )
        self.student = CustomUser.objects.create_user(
            username='stu1', password='test', role='student',
            grade='七年级', class_num='1', student_number='01', display_name='学生甲'
        )
        self.session = QuizSession.objects.create(
            title='测验', created_by=self.teacher,
            num_questions=10, difficulty_ratio={}
        )

    def test_create_submission(self):
        """基本字段保存"""
        sub = QuizSubmission.objects.create(
            user=self.student, session=self.session, grade='七年级',
            score=85.0, correct_count=8, total_count=10,
            answers_json='{"1": "A"}'
        )
        self.assertEqual(sub.score, 85.0)
        self.assertEqual(sub.grade, '七年级')
        self.assertEqual(sub.user, self.student)
        self.assertEqual(sub.session, self.session)

    def test_str_format(self):
        """__str__ = 学生名 - 小测名: 分数"""
        sub = QuizSubmission.objects.create(
            user=self.student, session=self.session, grade='七年级',
            score=100.0, correct_count=10, total_count=10, answers_json='{}'
        )
        self.assertIn('学生甲', str(sub))
        self.assertIn('100.0', str(sub))

    def test_grade_snapshot(self):
        """grade 字段提交时快照，不受后续用户 grade 变化影响"""
        self.student.grade = '八年级'
        self.student.save()
        sub = QuizSubmission.objects.create(
            user=self.student, session=self.session, grade=self.student.grade,
            score=50.0, correct_count=5, total_count=10, answers_json='{}'
        )
        # 快照值仍为八年级
        self.assertEqual(sub.grade, '八年级')

    def test_historical_attempts_use_null_current_marker(self):
        """同一小测可保留历史，但只能有一个当前有效作答。"""
        QuizSubmission.objects.create(
            user=self.student, session=self.session, grade='七年级',
            score=60.0, correct_count=6, total_count=10, answers_json='{}',
            attempt_no=1, current_marker=None, status='superseded',
        )
        QuizSubmission.objects.create(
            user=self.student, session=self.session, grade='七年级',
            score=80.0, correct_count=8, total_count=10, answers_json='{}',
            attempt_no=2, current_marker=True, status='submitted',
        )
        self.assertEqual(QuizSubmission.objects.filter(user=self.student).count(), 2)
        self.assertEqual(QuizSubmission.objects.filter(user=self.student, current_marker=True).count(), 1)
