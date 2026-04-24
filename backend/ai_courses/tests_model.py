"""
ai_courses Model + Serializer 单元测试
运行: cd backend && python manage.py test ai_courses.tests_model
"""
import os
import tempfile
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from ai_courses.models import Problem, Submission
from ai_courses.serializers import SubmissionCreateSerializer
from users.models import CustomUser


# ─── Model Tests ──────────────────────────────────────────────────────────

class ProblemModelTest(TestCase):
    """Problem 模型"""

    def test_str_returns_problem_id(self):
        """__str__ = problem_id"""
        p = Problem.objects.create(problem_id='problem_001', title='两数之和')
        self.assertEqual(str(p), 'problem_001')

    def test_create_ai_course_problem(self):
        """创建 AI课题目"""
        p = Problem.objects.create(
            problem_id='p_ai_1', title='Hello World', difficulty='easy', course='ai'
        )
        self.assertEqual(p.course, 'ai')
        self.assertEqual(p.difficulty, 'easy')

    def test_create_info_course_problem(self):
        """创建信息课题目"""
        p = Problem.objects.create(problem_id='p_info_1', course='info')
        self.assertEqual(p.course, 'info')

    def test_problem_id_unique(self):
        """problem_id 全局唯一"""
        Problem.objects.create(problem_id='unique_id', title='第一题')
        with self.assertRaises(Exception):  # IntegrityError
            Problem.objects.create(problem_id='unique_id', title='重复')

    def test_default_course_is_ai(self):
        """默认 course='ai'"""
        p = Problem.objects.create(problem_id='default_course')
        self.assertEqual(p.course, 'ai')

    def test_ordering_by_problem_id(self):
        """默认按 problem_id 升序"""
        Problem.objects.create(problem_id='z_problem')
        Problem.objects.create(problem_id='a_problem')
        Problem.objects.create(problem_id='m_problem')
        ids = list(Problem.objects.values_list('problem_id', flat=True))
        self.assertEqual(ids, ['a_problem', 'm_problem', 'z_problem'])


class ProblemGetTestCasesTest(TestCase):
    """Problem.get_test_cases() 和 get_test_count() — 读文件系统"""

    def _make_problem(self, course='ai', pid='test_prob'):
        return Problem.objects.create(problem_id=pid, course=course)

    def test_no_dir_returns_empty_list(self):
        """题目目录不存在 → []"""
        p = self._make_problem()
        self.assertEqual(p.get_test_cases(), [])
        self.assertEqual(p.get_test_count(), 0)

    def test_input_output_txt_pairs(self):
        """input1.txt + output1.txt 配对读取"""
        with tempfile.TemporaryDirectory() as tmpdir:
            prob_dir = os.path.join(tmpdir, 'test_prob')
            os.makedirs(prob_dir)
            with open(os.path.join(prob_dir, 'input1.txt'), 'w', encoding='utf-8') as f:
                f.write('1 2\n')
            with open(os.path.join(prob_dir, 'output1.txt'), 'w', encoding='utf-8') as f:
                f.write('3\n')

            with patch.object(Problem, 'get_problem_dir', return_value=prob_dir):
                p = self._make_problem()
                cases = p.get_test_cases()
                self.assertEqual(len(cases), 1)
                self.assertEqual(cases[0]['number'], 1)
                self.assertEqual(cases[0]['input'], '1 2\n')
                self.assertEqual(cases[0]['output'], '3')

    def test_multiple_test_cases(self):
        """多个测试点按 input 文件名排序"""
        with tempfile.TemporaryDirectory() as tmpdir:
            prob_dir = os.path.join(tmpdir, 'test_prob')
            os.makedirs(prob_dir)
            for i, (inp, out) in enumerate([('a\n', 'A\n'), ('b\n', 'B\n'), ('c\n', 'C\n')], 1):
                with open(os.path.join(prob_dir, f'input{i}.txt'), 'w') as f:
                    f.write(inp)
                with open(os.path.join(prob_dir, f'output{i}.txt'), 'w') as f:
                    f.write(out.strip())

            with patch.object(Problem, 'get_problem_dir', return_value=prob_dir):
                p = self._make_problem()
                cases = p.get_test_cases()
                self.assertEqual(len(cases), 3)
                self.assertEqual(cases[0]['input'], 'a\n')
                self.assertEqual(cases[2]['input'], 'c\n')

    def test_n_in_n_out_format(self):
        """1.in / 1.out 格式"""
        with tempfile.TemporaryDirectory() as tmpdir:
            prob_dir = os.path.join(tmpdir, 'test_prob')
            os.makedirs(prob_dir)
            with open(os.path.join(prob_dir, '1.in'), 'w', encoding='utf-8') as f:
                f.write('hello')
            with open(os.path.join(prob_dir, '1.out'), 'w', encoding='utf-8') as f:
                f.write('HELLO')

            with patch.object(Problem, 'get_problem_dir', return_value=prob_dir):
                p = self._make_problem()
                cases = p.get_test_cases()
                self.assertEqual(len(cases), 1)
                self.assertEqual(cases[0]['input'], 'hello')
                self.assertEqual(cases[0]['output'], 'HELLO')

    def test_get_test_count_calls_get_test_cases(self):
        """get_test_count = len(get_test_cases())"""
        with tempfile.TemporaryDirectory() as tmpdir:
            prob_dir = os.path.join(tmpdir, 'test_prob')
            os.makedirs(prob_dir)
            for i in range(5):
                with open(os.path.join(prob_dir, f'input{i+1}.txt'), 'w') as f:
                    f.write('x')
                with open(os.path.join(prob_dir, f'output{i+1}.txt'), 'w') as f:
                    f.write('y')

            with patch.object(Problem, 'get_problem_dir', return_value=prob_dir):
                p = self._make_problem()
class ProblemSyncFromDiskTest(TestCase):
    """Problem.sync_from_disk() 类方法 — mock os.* 磁盘操作"""

    def test_no_dir_returns_empty(self):
        """problems_dir 不存在 → ([], [])"""
        with patch('ai_courses.models.os.path.exists', return_value=False):
            created, updated = Problem.sync_from_disk()
            self.assertEqual(created, [])
            self.assertEqual(updated, [])

    def test_sync_ai_problems_from_ai_subdir(self):
        """problems/ai/problemX/ → course='ai'"""
        with tempfile.TemporaryDirectory() as tmpdir:
            prob_dir = os.path.join(tmpdir, 'ai', 'problem_new_ai')
            os.makedirs(prob_dir)
            with open(os.path.join(prob_dir, 'description.txt'), 'w', encoding='utf-8') as f:
                f.write('求和题描述内容')

            with patch('ai_courses.models.settings') as mock_settings:
                mock_settings.PROBLEMS_DIR = tmpdir
                created, updated = Problem.sync_from_disk()

            self.assertIn('problem_new_ai', created)
            p = Problem.objects.get(problem_id='problem_new_ai')
            self.assertEqual(p.course, 'ai')
            self.assertEqual(p.description, '求和题描述内容')

    def test_sync_info_problems_from_root(self):
        """problems/problemX/（根目录） → course='info'"""
        with tempfile.TemporaryDirectory() as tmpdir:
            prob_dir = os.path.join(tmpdir, 'problem_info')
            os.makedirs(prob_dir)
            with open(os.path.join(prob_dir, 'description.txt'), 'w', encoding='utf-8') as f:
                f.write('信息课描述内容')

            with patch('ai_courses.models.settings') as mock_settings:
                mock_settings.PROBLEMS_DIR = tmpdir
                created, updated = Problem.sync_from_disk()

            self.assertIn('problem_info', created)
            p = Problem.objects.get(problem_id='problem_info')
            self.assertEqual(p.course, 'info')

    def test_sync_updates_existing(self):
        """已存在题目再次 sync → update，不重复创建"""
        Problem.objects.create(problem_id='problem_existing', title='旧标题', course='ai')
        with tempfile.TemporaryDirectory() as tmpdir:
            prob_dir = os.path.join(tmpdir, 'ai', 'problem_existing')
            os.makedirs(prob_dir)
            with open(os.path.join(prob_dir, 'description.txt'), 'w', encoding='utf-8') as f:
                f.write('更新后描述')

            with patch('ai_courses.models.settings') as mock_settings:
                mock_settings.PROBLEMS_DIR = tmpdir
                created, updated = Problem.sync_from_disk()

            self.assertEqual(created, [])
            self.assertIn('problem_existing', updated)
            p = Problem.objects.get(problem_id='problem_existing')
            self.assertEqual(p.description, '更新后描述')

    def test_non_problem_dir_ignored(self):
        """不以 'problem' 开头的目录被忽略"""
        with tempfile.TemporaryDirectory() as tmpdir:
            sub_dir = os.path.join(tmpdir, 'ai')
            os.makedirs(sub_dir)
            os.makedirs(os.path.join(sub_dir, 'random_folder'))  # 不以 problem 开头 → 忽略

            with patch('ai_courses.models.settings') as mock_settings:
                mock_settings.PROBLEMS_DIR = tmpdir
                created, updated = Problem.sync_from_disk()
            self.assertEqual(created, [])


class SubmissionModelTest(TestCase):
    """Submission 模型"""

    def setUp(self):
        self.student = CustomUser.objects.create_user(
            username='stu_sub', password='x', role='student',
            grade='七年级', class_num='1', student_number='01'
        )
        self.prob = Problem.objects.create(problem_id='subj_prob', course='ai')

    def test_str_format(self):
        """__str__ = submission id + user + score"""
        sub = Submission.objects.create(
            user=self.student, problem=self.prob, code='print(1)',
            score=100.0, status='accepted'
        )
        s = str(sub)
        self.assertIn('stu_sub', s)
        self.assertIn('100.0', s)

    def test_create_full_fields(self):
        """所有字段正确保存"""
        sub = Submission.objects.create(
            user=self.student, problem=self.prob, code='x=1\nprint(x)',
            score=85.5, status='wrong_answer', error_message='输出格式错误'
        )
        self.assertEqual(sub.score, 85.5)
        self.assertEqual(sub.status, 'wrong_answer')
        self.assertEqual(sub.error_message, '输出格式错误')

    def test_multiple_submissions_same_problem(self):
        """同一学生同一题目可多次提交"""
        Submission.objects.create(user=self.student, problem=self.prob, code='v1', score=60.0, status='wrong')
        Submission.objects.create(user=self.student, problem=self.prob, code='v2', score=100.0, status='accepted')
        self.assertEqual(Submission.objects.filter(user=self.student, problem=self.prob).count(), 2)

    def test_ordering_by_submitted_at_desc(self):
        """默认按 submitted_at 降序（最新在前）"""
        sub1 = Submission.objects.create(user=self.student, problem=self.prob, code='c1', score=50.0, status='wrong')
        sub2 = Submission.objects.create(user=self.student, problem=self.prob, code='c2', score=80.0, status='wrong')
        ids = list(Submission.objects.values_list('id', flat=True))
        self.assertEqual(ids, [sub2.id, sub1.id])  # 最新在前面


# ─── Serializer Tests ──────────────────────────────────────────────────────

class SubmissionCreateSerializerTest(TestCase):
    """SubmissionCreateSerializer 校验"""

    def test_valid_data(self):
        """合法 code + problem_id → is_valid=True"""
        s = SubmissionCreateSerializer(data={'problem_id': 'p1', 'code': 'print("hello")'})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data['code'], 'print("hello")')

    def test_empty_code_fails(self):
        """空字符串 → ValidationError"""
        s = SubmissionCreateSerializer(data={'problem_id': 'p1', 'code': ''})
        self.assertFalse(s.is_valid())
        self.assertIn('code', s.errors)
        self.assertIn('不能为空', str(s.errors['code'][0]))

    def test_whitespace_only_code_fails(self):
        """纯空白 code → ValidationError"""
        s = SubmissionCreateSerializer(data={'problem_id': 'p1', 'code': '   \n\t  '})
        self.assertFalse(s.is_valid())
        self.assertIn('code', s.errors)

    def test_strips_whitespace(self):
        """有效 code 首尾空白被 strip"""
        s = SubmissionCreateSerializer(data={'problem_id': 'p1', 'code': '  print(1)  \n'})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data['code'], 'print(1)')

    def test_missing_problem_id(self):
        """缺少 problem_id → 校验失败"""
        s = SubmissionCreateSerializer(data={'code': 'print(1)'})
        self.assertFalse(s.is_valid())
        self.assertIn('problem_id', s.errors)

    def test_missing_code(self):
        """缺少 code → 校验失败"""
        s = SubmissionCreateSerializer(data={'problem_id': 'p1'})
        self.assertFalse(s.is_valid())
        self.assertIn('code', s.errors)
