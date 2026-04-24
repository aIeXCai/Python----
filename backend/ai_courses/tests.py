"""
ai_courses API 测试套件
运行: cd backend && python manage.py test ai_courses
"""
import json
from unittest.mock import patch, MagicMock
from rest_framework.test import APITestCase
from rest_framework.authtoken.models import Token
from users.models import CustomUser
from .models import Problem, Submission


# ─── 测试辅助 ──────────────────────────────────────────────────────────────

_counter = [0]

def make_teacher(username=None, managed_grade='七年级'):
    _counter[0] += 1
    u = CustomUser.objects.create_user(
        username=username or f'ai_teacher{_counter[0]}',
        password='test123', role='teacher',
        display_name='AI老师', managed_grade=managed_grade
    )
    return u

def make_student(grade='七年级', class_num='1', student_number='01', display_name=None):
    _counter[0] += 1
    u = CustomUser.objects.create_user(
        username=f'ai_stu_{grade}{class_num}{student_number}{_counter[0]}',
        password='test123', role='student',
        grade=grade, class_num=class_num, student_number=student_number,
        display_name=display_name or f'AI学生{_counter[0]}',
        managed_grade=grade
    )
    return u

def get_token(user):
    return Token.objects.get_or_create(user=user)[0].key


# ─── 学生端：题目列表 ─────────────────────────────────────────────────────

class ProblemListViewTest(APITestCase):
    """GET /api/ai/problems/"""

    def setUp(self):
        self.student = make_student()
        self.token = get_token(self.student)
        self.prob1 = Problem.objects.create(
            problem_id='p1', title='题目1', difficulty='easy', course='ai'
        )
        self.prob2 = Problem.objects.create(
            problem_id='p2', title='题目2', difficulty='hard', course='ai'
        )
        self.prob3 = Problem.objects.create(
            problem_id='p3', title='信息课题目', difficulty='medium', course='info'
        )

    def test_list_all_ai_problems(self):
        """默认列出 ai 课题目"""
        resp = self.client.get('/api/ai/problems/', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 2)
        pids = [p['problem_id'] for p in resp.data]
        self.assertIn('p1', pids)
        self.assertIn('p2', pids)
        self.assertNotIn('p3', pids)

    def test_filter_by_course(self):
        """?course=info 列出信息课题目"""
        resp = self.client.get('/api/ai/problems/?course=info', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['problem_id'], 'p3')

    def test_returns_test_count(self):
        """返回 test_count 字段（无测试文件时为0）"""
        resp = self.client.get('/api/ai/problems/', HTTP_AUTHORIZATION=f'Token {self.token}')
        for p in resp.data:
            self.assertIn('test_count', p)
            self.assertEqual(p['test_count'], 0)  # 无真实测试文件

    def test_unauthenticated_rejected(self):
        """未登录返回 401"""
        resp = self.client.get('/api/ai/problems/')
        self.assertEqual(resp.status_code, 401)


# ─── 学生端：题目详情 ─────────────────────────────────────────────────────

class ProblemDetailViewTest(APITestCase):
    """GET /api/ai/problems/<problem_id>/"""

    def setUp(self):
        self.student = make_student()
        self.token = get_token(self.student)
        self.prob = Problem.objects.create(
            problem_id='detail_test', title='详情测试', difficulty='medium',
            description='这是描述', course='ai'
        )

    @patch.object(Problem, 'get_test_cases')
    def test_get_detail_success(self, mock_get_cases):
        """获取详情成功"""
        mock_get_cases.return_value = [
            {'number': 1, 'input': '1 2', 'output': '3'},
        ]
        resp = self.client.get(
            '/api/ai/problems/detail_test/',
            HTTP_AUTHORIZATION=f'Token {self.token}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['problem_id'], 'detail_test')
        self.assertEqual(resp.data['description'], '这是描述')
        self.assertEqual(len(resp.data['test_cases']), 1)

    @patch.object(Problem, 'get_test_cases')
    def test_get_detail_no_test_cases(self, mock_get_cases):
        """无测试文件时返回空列表"""
        mock_get_cases.return_value = []
        resp = self.client.get(
            '/api/ai/problems/detail_test/',
            HTTP_AUTHORIZATION=f'Token {self.token}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['test_cases'], [])

    def test_get_nonexistent_problem(self):
        """不存在的题目返回 404"""
        resp = self.client.get(
            '/api/ai/problems/nonexistent/',
            HTTP_AUTHORIZATION=f'Token {self.token}'
        )
        self.assertEqual(resp.status_code, 404)

    def test_get_problem_wrong_course(self):
        """course 不匹配时返回 404（因为按 problem_id+course 查询）"""
        resp = self.client.get(
            '/api/ai/problems/detail_test/?course=info',
            HTTP_AUTHORIZATION=f'Token {self.token}'
        )
        self.assertEqual(resp.status_code, 404)  # detail_test 是 ai 课


# ─── 学生端：提交代码 ─────────────────────────────────────────────────────

class SubmissionViewTest(APITestCase):
    """POST /api/ai/submissions/"""

    def setUp(self):
        self.student = make_student()
        self.token = get_token(self.student)
        self.prob = Problem.objects.create(
            problem_id='submit_test', title='提交测试', course='ai'
        )

    @patch('ai_courses.views.grade_submission')
    def test_submit_code_correct(self, mock_grade):
        """代码完全正确得分100"""
        mock_grade.return_value = (True, '全部通过\n测试点1: 通过\n测试点2: 通过', 100.0)
        resp = self.client.post('/api/ai/submissions/', {
            'problem_id': 'submit_test',
            'code': 'print("hello")',
        }, format='json', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['score'], 100.0)
        self.assertEqual(resp.data['status'], 'accepted')
        self.assertIn('submission_id', resp.data)

    @patch('ai_courses.views.grade_submission')
    def test_submit_code_wrong_answer(self, mock_grade):
        """ok=False → status='error'（批改判定失败）"""
        mock_grade.return_value = (False, '答案错误', 0.0)
        resp = self.client.post('/api/ai/submissions/', {
            'problem_id': 'submit_test',
            'code': 'wrong answer',
        }, format='json', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['score'], 0.0)
        self.assertEqual(resp.data['status'], 'error')

    @patch('ai_courses.views.grade_submission')
    def test_submit_code_partial_score(self, mock_grade):
        """ok=True + score<100 → status='wrong_answer'"""
        mock_grade.return_value = (True, '部分通过', 50.0)
        resp = self.client.post('/api/ai/submissions/', {
            'problem_id': 'submit_test',
            'code': 'half right',
        }, format='json', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['score'], 50.0)
        self.assertEqual(resp.data['status'], 'wrong_answer')

    @patch('ai_courses.views.grade_submission')
    def test_submit_creates_submission_record(self, mock_grade):
        """提交后数据库有记录"""
        mock_grade.return_value = (True, 'ok', 100.0)
        resp = self.client.post('/api/ai/submissions/', {
            'problem_id': 'submit_test',
            'code': 'correct',
        }, format='json', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Submission.objects.count(), 1)
        sub = Submission.objects.first()
        self.assertEqual(sub.user, self.student)
        self.assertEqual(sub.score, 100.0)

    @patch('ai_courses.views.grade_submission')
    def test_submit_saves_code(self, mock_grade):
        """提交后代码被保存"""
        mock_grade.return_value = (True, 'ok', 100.0)
        resp = self.client.post('/api/ai/submissions/', {
            'problem_id': 'submit_test',
            'code': 'my_code_here',
        }, format='json', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Submission.objects.first().code, 'my_code_here')

    def test_submit_nonexistent_problem(self):
        """题目不存在"""
        resp = self.client.post('/api/ai/submissions/', {
            'problem_id': 'no_such_problem',
            'code': 'code',
        }, format='json', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 404)

    def test_submit_empty_code(self):
        """空代码返回 400"""
        resp = self.client.post('/api/ai/submissions/', {
            'problem_id': 'submit_test',
            'code': '   ',
        }, format='json', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 400)

    def test_submit_missing_code(self):
        """缺少 code 字段"""
        resp = self.client.post('/api/ai/submissions/', {
            'problem_id': 'submit_test',
        }, format='json', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 400)

    def test_submit_unauthenticated(self):
        """未登录返回 401"""
        resp = self.client.post('/api/ai/submissions/', {
            'problem_id': 'submit_test', 'code': 'code'
        }, format='json')
        self.assertEqual(resp.status_code, 401)

    @patch('ai_courses.views.grade_submission')
    def test_submit_grade_exception_returns_500(self, mock_grade):
        """批改系统异常返回 500"""
        mock_grade.side_effect = Exception('grading system error')
        resp = self.client.post('/api/ai/submissions/', {
            'problem_id': 'submit_test',
            'code': 'bad code',
        }, format='json', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 500)
        self.assertIn('批改系统错误', resp.data['detail'])


# ─── 学生端：提交历史 ─────────────────────────────────────────────────────

class SubmissionHistoryViewTest(APITestCase):
    """GET /api/ai/submissions/history/"""

    def setUp(self):
        self.student = make_student()
        self.token = get_token(self.student)
        self.prob = Problem.objects.create(
            problem_id='history_test', title='历史测试', course='ai'
        )
        self.sub1 = Submission.objects.create(
            user=self.student, problem=self.prob, code='v1',
            score=60.0, status='wrong_answer'
        )
        self.sub2 = Submission.objects.create(
            user=self.student, problem=self.prob, code='v2',
            score=100.0, status='accepted'
        )

    def test_get_history_all(self):
        """返回该学生全部历史"""
        resp = self.client.get(
            '/api/ai/submissions/history/',
            HTTP_AUTHORIZATION=f'Token {self.token}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 2)

    def test_get_history_filter_by_problem(self):
        """?problem_id= 过滤"""
        resp = self.client.get(
            '/api/ai/submissions/history/?problem_id=history_test',
            HTTP_AUTHORIZATION=f'Token {self.token}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 2)

    def test_get_history_only_own(self):
        """只返回自己的提交，不包含其他学生的"""
        other = make_student(display_name='其他学生')
        other_sub = Submission.objects.create(
            user=other, problem=self.prob, code='other',
            score=50.0, status='wrong_answer'
        )
        resp = self.client.get(
            '/api/ai/submissions/history/',
            HTTP_AUTHORIZATION=f'Token {self.token}'
        )
        pids = [s['id'] for s in resp.data]
        self.assertNotIn(other_sub.id, pids)

    def test_history_limited_to_20(self):
        """最多返回20条"""
        # 创建21条
        prob2 = Problem.objects.create(problem_id='p_many', title='多题', course='ai')
        for i in range(21):
            Submission.objects.create(
                user=self.student, problem=prob2, code=f'code{i}',
                score=50.0, status='wrong_answer'
            )
        resp = self.client.get(
            '/api/ai/submissions/history/',
            HTTP_AUTHORIZATION=f'Token {self.token}'
        )
        self.assertLessEqual(len(resp.data), 20)

    def test_unauthenticated_rejected(self):
        """未登录返回 401"""
        resp = self.client.get('/api/ai/submissions/history/')
        self.assertEqual(resp.status_code, 401)


# ─── 学生端：成绩查看 ─────────────────────────────────────────────────────

class StudentScoresViewTest(APITestCase):
    """GET /api/ai/scores/"""

    def setUp(self):
        self.student = make_student()
        self.token = get_token(self.student)
        self.prob1 = Problem.objects.create(problem_id='s1', title='得分题1', course='ai')
        self.prob2 = Problem.objects.create(problem_id='s2', title='得分题2', course='ai')
        self.prob3 = Problem.objects.create(problem_id='s3', title='信息课题', course='info')

        # 学生对 prob1 提交了3次：60, 80, 100 → 最高100
        Submission.objects.create(user=self.student, problem=self.prob1, code='v1', score=60.0, status='wrong')
        Submission.objects.create(user=self.student, problem=self.prob1, code='v2', score=80.0, status='wrong')
        Submission.objects.create(user=self.student, problem=self.prob1, code='v3', score=100.0, status='accepted')
        # 对 prob2 提交1次：50
        Submission.objects.create(user=self.student, problem=self.prob2, code='c', score=50.0, status='wrong')
        # prob3 是信息课，不应计入 ai 课成绩
        Submission.objects.create(user=self.student, problem=self.prob3, code='c', score=90.0, status='accepted')

    def test_scores_returns_best_per_problem(self):
        """每题只返回最高分"""
        resp = self.client.get('/api/ai/scores/', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        # prob1 最高100, prob2 最高50, prob3 是 info 课不算
        scores = {s['problem_id']: s['best_score'] for s in resp.data}
        self.assertEqual(scores.get('s1'), 100.0)
        self.assertEqual(scores.get('s2'), 50.0)
        self.assertNotIn('s3', scores)

    def test_scores_returns_attempts(self):
        """返回尝试次数"""
        resp = self.client.get('/api/ai/scores/', HTTP_AUTHORIZATION=f'Token {self.token}')
        scores = {s['problem_id']: s['attempts'] for s in resp.data}
        self.assertEqual(scores['s1'], 3)
        self.assertEqual(scores['s2'], 1)

    def test_scores_filter_by_problem_id(self):
        """?problem_id= 过滤"""
        resp = self.client.get('/api/ai/scores/?problem_id=s1',
                                HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['best_score'], 100.0)

    def test_scores_filter_by_course(self):
        """?course=info 只看信息课"""
        resp = self.client.get('/api/ai/scores/?course=info',
                                HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        pids = [s['problem_id'] for s in resp.data]
        self.assertIn('s3', pids)
        self.assertNotIn('s1', pids)

    def test_scores_status_completed_threshold(self):
        """>=80 分为 completed，否则 attempted"""
        resp = self.client.get('/api/ai/scores/', HTTP_AUTHORIZATION=f'Token {self.token}')
        scores = {s['problem_id']: s['status'] for s in resp.data}
        self.assertEqual(scores['s1'], 'completed')   # 100 >= 80
        self.assertEqual(scores['s2'], 'attempted')   # 50 < 80

    def test_unauthenticated_rejected(self):
        """未登录返回 401"""
        resp = self.client.get('/api/ai/scores/')
        self.assertEqual(resp.status_code, 401)


# ─── 学生端：学习统计 ─────────────────────────────────────────────────────

class StudentStatsViewTest(APITestCase):
    """GET /api/ai/stats/"""

    def setUp(self):
        self.student = make_student()
        self.token = get_token(self.student)
        self.prob1 = Problem.objects.create(problem_id='stat1', course='ai')
        self.prob2 = Problem.objects.create(problem_id='stat2', course='ai')
        Submission.objects.create(user=self.student, problem=self.prob1, score=100.0, code='c')
        Submission.objects.create(user=self.student, problem=self.prob1, score=80.0, code='c')  # 第二次不改变
        Submission.objects.create(user=self.student, problem=self.prob2, score=50.0, code='c')

    def test_stats_total_problems(self):
        """总题目数"""
        resp = self.client.get('/api/ai/stats/', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total_problems'], 2)

    def test_stats_completed_problems(self):
        """>=80分的已完成题目数（按题去重）"""
        resp = self.client.get('/api/ai/stats/', HTTP_AUTHORIZATION=f'Token {self.token}')
        # prob1 最高分100(>=80) completed, prob2 最高分50(<80) attempted
        self.assertEqual(resp.data['completed_problems'], 1)

    def test_stats_average_score(self):
        """平均分（每题取最高分后再平均）"""
        resp = self.client.get('/api/ai/stats/', HTTP_AUTHORIZATION=f'Token {self.token}')
        # (100 + 50) / 2 = 75.0
        self.assertEqual(resp.data['average_score'], 75.0)

    def test_stats_rank(self):
        """排名（目前固定返回1）"""
        resp = self.client.get('/api/ai/stats/', HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.data['rank'], 1)

    def test_stats_filter_by_course(self):
        """?course=info 只看信息课"""
        prob3 = Problem.objects.create(problem_id='stat3', course='info')
        Submission.objects.create(user=self.student, problem=prob3, score=90.0, code='c')
        resp = self.client.get('/api/ai/stats/?course=info',
                                HTTP_AUTHORIZATION=f'Token {self.token}')
        self.assertEqual(resp.data['total_problems'], 1)
        self.assertEqual(resp.data['completed_problems'], 1)


# ─── 老师端：管理后台概览 ───────────────────────────────────────────────

class AdminDashboardViewTest(APITestCase):
    """GET /api/ai/admin/dashboard/"""

    def setUp(self):
        self.teacher = make_teacher()
        self.teacher_token = get_token(self.teacher)
        self.student = make_student()
        Problem.objects.create(problem_id='dash1', course='ai')
        Submission.objects.create(user=self.student, problem_id=1, score=85.0, code='c')

    def test_dashboard_returns_stats(self):
        """返回统计数据"""
        resp = self.client.get(
            '/api/ai/admin/dashboard/',
            HTTP_AUTHORIZATION=f'Token {self.teacher_token}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('total_students', resp.data)
        self.assertIn('total_problems', resp.data)
        self.assertIn('today_submissions', resp.data)
        self.assertIn('avg_score', resp.data)

    def test_dashboard_teacher_only(self):
        """学生不能访问"""
        resp = self.client.get(
            '/api/ai/admin/dashboard/',
            HTTP_AUTHORIZATION=f'Token {get_token(self.student)}'
        )
        self.assertEqual(resp.status_code, 403)

    def test_dashboard_unauthenticated(self):
        """未登录返回 401"""
        resp = self.client.get('/api/ai/admin/dashboard/')
        self.assertEqual(resp.status_code, 401)


# ─── 老师端：题目管理 ─────────────────────────────────────────────────────

class AdminProblemListViewTest(APITestCase):
    """GET/POST /api/ai/admin/problems/"""

    def setUp(self):
        self.teacher = make_teacher()
        self.teacher_token = get_token(self.teacher)
        self.student = make_student()
        Problem.objects.create(problem_id='admin_p1', course='ai')
        Problem.objects.create(problem_id='admin_p2', course='info')

    def test_list_all_problems(self):
        """GET 默认列出 ai 课题目"""
        resp = self.client.get(
            '/api/ai/admin/problems/',
            HTTP_AUTHORIZATION=f'Token {self.teacher_token}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['problem_id'], 'admin_p1')

    def test_list_filter_by_course(self):
        """?course=info"""
        resp = self.client.get(
            '/api/ai/admin/problems/?course=info',
            HTTP_AUTHORIZATION=f'Token {self.teacher_token}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['problem_id'], 'admin_p2')

    @patch.object(Problem, 'sync_from_disk')
    def test_sync_from_disk(self, mock_sync):
        """POST 触发从磁盘同步"""
        mock_sync.return_value = (['new1', 'new2'], ['updated1'])
        resp = self.client.post(
            '/api/ai/admin/problems/',
            HTTP_AUTHORIZATION=f'Token {self.teacher_token}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['created'], ['new1', 'new2'])
        self.assertEqual(resp.data['updated'], ['updated1'])

    def test_list_student_forbidden(self):
        """学生不能 GET"""
        resp = self.client.get(
            '/api/ai/admin/problems/',
            HTTP_AUTHORIZATION=f'Token {get_token(self.student)}'
        )
        self.assertEqual(resp.status_code, 403)

    def test_post_student_forbidden(self):
        """学生不能 POST sync"""
        resp = self.client.post(
            '/api/ai/admin/problems/',
            HTTP_AUTHORIZATION=f'Token {get_token(self.student)}'
        )
        self.assertEqual(resp.status_code, 403)


class AdminProblemDetailViewTest(APITestCase):
    """GET/DELETE /api/ai/admin/problems/<problem_id>/"""

    def setUp(self):
        self.teacher = make_teacher()
        self.teacher_token = get_token(self.teacher)
        self.student = make_student()
        self.prob = Problem.objects.create(
            problem_id='detail_admin', title='管理详情', course='ai'
        )

    def test_get_problem_detail(self):
        """GET 返回题目详情"""
        resp = self.client.get(
            '/api/ai/admin/problems/detail_admin/',
            HTTP_AUTHORIZATION=f'Token {self.teacher_token}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['problem_id'], 'detail_admin')
        self.assertEqual(resp.data['title'], '管理详情')

    def test_delete_problem(self):
        """DELETE 删除题目"""
        resp = self.client.delete(
            '/api/ai/admin/problems/detail_admin/',
            HTTP_AUTHORIZATION=f'Token {self.teacher_token}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Problem.objects.filter(problem_id='detail_admin').exists())

    def test_get_nonexistent(self):
        """GET 不存在的题目"""
        resp = self.client.get(
            '/api/ai/admin/problems/no_such/',
            HTTP_AUTHORIZATION=f'Token {self.teacher_token}'
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete_nonexistent(self):
        """DELETE 不存在的题目"""
        resp = self.client.delete(
            '/api/ai/admin/problems/no_such/',
            HTTP_AUTHORIZATION=f'Token {self.teacher_token}'
        )
        self.assertEqual(resp.status_code, 404)

    def test_student_forbidden(self):
        """学生不能操作"""
        token = get_token(self.student)
        for method, url in [
            ('get', '/api/ai/admin/problems/detail_admin/'),
            ('delete', '/api/ai/admin/problems/detail_admin/'),
        ]:
            fn = getattr(self.client, method)
            resp = fn(url, HTTP_AUTHORIZATION=f'Token {token}')
            self.assertEqual(resp.status_code, 403)


# ─── 老师端：学生列表 ─────────────────────────────────────────────────────

class AdminStudentListViewTest(APITestCase):
    """GET /api/ai/admin/students/"""

    def setUp(self):
        self.teacher = make_teacher()
        self.teacher_token = get_token(self.teacher)
        self.stu1 = make_student(grade='七年级', class_num='1', student_number='01', display_name='学生A')
        self.stu2 = make_student(grade='八年级', class_num='2', student_number='03', display_name='学生B')

    def test_list_students(self):
        """返回所有学生"""
        resp = self.client.get(
            '/api/ai/admin/students/',
            HTTP_AUTHORIZATION=f'Token {self.teacher_token}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 2)

    def test_filter_by_grade(self):
        """?grade= 筛选"""
        resp = self.client.get(
            '/api/ai/admin/students/?grade=七年级',
            HTTP_AUTHORIZATION=f'Token {self.teacher_token}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['display_name'], '学生A')

    def test_filter_by_class_num(self):
        """?class_num= 筛选"""
        resp = self.client.get(
            '/api/ai/admin/students/?class_num=2',
            HTTP_AUTHORIZATION=f'Token {self.teacher_token}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['display_name'], '学生B')

    def test_sort_by_grade_asc(self):
        """默认按 grade 升序"""
        resp = self.client.get(
            '/api/ai/admin/students/',
            HTTP_AUTHORIZATION=f'Token {self.teacher_token}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data[0]['grade'], '七年级')

    def test_sort_by_student_number_desc(self):
        """?sort_by=student_number&order=desc"""
        resp = self.client.get(
            '/api/ai/admin/students/?sort_by=student_number&order=desc',
            HTTP_AUTHORIZATION=f'Token {self.teacher_token}'
        )
        self.assertEqual(resp.status_code, 200)

    def test_student_forbidden(self):
        """学生不能访问"""
        resp = self.client.get(
            '/api/ai/admin/students/',
            HTTP_AUTHORIZATION=f'Token {get_token(self.stu1)}'
        )
        self.assertEqual(resp.status_code, 403)


# ─── 老师端：学生成绩矩阵 ─────────────────────────────────────────────────

class AdminStudentScoresViewTest(APITestCase):
    """GET /api/ai/admin/scores/"""

    def setUp(self):
        self.teacher = make_teacher()
        self.teacher_token = get_token(self.teacher)
        self.stu1 = make_student(grade='七年级', class_num='1', student_number='01', display_name='甲')
        self.stu2 = make_student(grade='七年级', class_num='1', student_number='02', display_name='乙')

        self.prob1 = Problem.objects.create(problem_id='score_p1', title='题1', course='ai')
        self.prob2 = Problem.objects.create(problem_id='score_p2', title='题2', course='ai')

        # 甲: p1得80, p2得100
        Submission.objects.create(user=self.stu1, problem=self.prob1, score=60.0, code='c')
        Submission.objects.create(user=self.stu1, problem=self.prob1, score=80.0, code='c')
        Submission.objects.create(user=self.stu1, problem=self.prob2, score=100.0, code='c')
        # 乙: p1得70
        Submission.objects.create(user=self.stu2, problem=self.prob1, score=70.0, code='c')

    def test_scores_returns_matrix(self):
        """返回学生×题目成绩矩阵"""
        resp = self.client.get(
            '/api/ai/admin/scores/',
            HTTP_AUTHORIZATION=f'Token {self.teacher_token}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('students', resp.data)
        self.assertIn('problems', resp.data)

    def test_scores_returns_best_per_student_per_problem(self):
        """每学生每题取最高分"""
        resp = self.client.get(
            '/api/ai/admin/scores/',
            HTTP_AUTHORIZATION=f'Token {self.teacher_token}'
        )
        stu_map = {s['display_name']: s for s in resp.data['students']}
        self.assertEqual(stu_map['甲']['scores'][0]['score'], 80.0)  # p1最高80
        self.assertEqual(stu_map['甲']['scores'][1]['score'], 100.0)  # p2最高100

    def test_scores_best_score_global(self):
        """best_score 是全局最高"""
        resp = self.client.get(
            '/api/ai/admin/scores/',
            HTTP_AUTHORIZATION=f'Token {self.teacher_token}'
        )
        stu_map = {s['display_name']: s for s in resp.data['students']}
        self.assertEqual(stu_map['甲']['best_score'], 100.0)
        self.assertEqual(stu_map['乙']['best_score'], 70.0)

    def test_scores_filter_by_grade(self):
        """?grade= 筛选"""
        resp = self.client.get(
            '/api/ai/admin/scores/?grade=七年级',
            HTTP_AUTHORIZATION=f'Token {self.teacher_token}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['students']), 2)

    def test_scores_filter_by_class_num(self):
        """?class_num= 筛选"""
        resp = self.client.get(
            '/api/ai/admin/scores/?class_num=1',
            HTTP_AUTHORIZATION=f'Token {self.teacher_token}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['students']), 2)

    def test_scores_filter_by_problem_id(self):
        """?problem_id= 只返回指定题"""
        resp = self.client.get(
            '/api/ai/admin/scores/?problem_id=score_p1',
            HTTP_AUTHORIZATION=f'Token {self.teacher_token}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['problems']), 1)
        self.assertEqual(resp.data['problems'][0]['problem_id'], 'score_p1')

    def test_scores_filter_by_course_type(self):
        """?course_type=ai 只看 ai 课"""
        resp = self.client.get(
            '/api/ai/admin/scores/?course_type=ai',
            HTTP_AUTHORIZATION=f'Token {self.teacher_token}'
        )
        self.assertEqual(resp.status_code, 200)
        pids = [p['problem_id'] for p in resp.data['problems']]
        self.assertIn('score_p1', pids)
        self.assertIn('score_p2', pids)

    def test_scores_student_forbidden(self):
        """学生不能访问"""
        resp = self.client.get(
            '/api/ai/admin/scores/',
            HTTP_AUTHORIZATION=f'Token {get_token(self.stu1)}'
        )
        self.assertEqual(resp.status_code, 403)

    def test_scores_unauthenticated(self):
        """未登录返回 401"""
        resp = self.client.get('/api/ai/admin/scores/')
        self.assertEqual(resp.status_code, 401)

    def test_scores_all_students_appear_even_without_submissions(self):
        """即使没有提交记录也显示该学生（分数为空）"""
        stu3 = make_student(grade='八年级', class_num='3', student_number='10', display_name='丙')
        resp = self.client.get(
            '/api/ai/admin/scores/?grade=八年级',
            HTTP_AUTHORIZATION=f'Token {self.teacher_token}'
        )
        self.assertEqual(resp.status_code, 200)
        names = [s['display_name'] for s in resp.data['students']]
        self.assertIn('丙', names)
        # 丙没有提交，scores 应为空
        c_scores = next(s['scores'] for s in resp.data['students'] if s['display_name'] == '丙')
        self.assertEqual(c_scores, [])
