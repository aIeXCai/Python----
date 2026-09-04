import uuid
from unittest.mock import patch

from django.core.cache import cache
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from ai_courses.models import Problem, Submission
from execution.constants import STATUS_RUNNING, STATUS_SUCCEEDED, TASK_TYPE_GRADE, TASK_TYPE_RUN
from execution.models import ExecutionTask
from users.models import CustomUser


class PublicExecutionApiTest(APITestCase):
    def setUp(self):
        cache.clear()
        self.student = CustomUser.objects.create_user(
            username='queue_student', password='test-pass', role='student',
            grade='七年级', class_num='1', student_number='01',
        )
        self.other_student = CustomUser.objects.create_user(
            username='other_queue_student', password='test-pass', role='student',
            grade='七年级', class_num='1', student_number='02',
        )
        token = Token.objects.create(user=self.student)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        self.problem = Problem.objects.create(problem_id='queue_problem', course='ai')
        self.cases = [{'number': 7, 'input': '1\n', 'output': '2'}]

    def post_run(self, *, code='print(1)', stdin='', key=None):
        headers = {'HTTP_IDEMPOTENCY_KEY': key} if key else {}
        return self.client.post('/api/ai/run_code/', {'code': code, 'stdin': stdin}, format='json', **headers)

    def post_grade(self, *, code='print(2)', key=None):
        headers = {'HTTP_IDEMPOTENCY_KEY': key} if key else {}
        with patch.object(Problem, 'get_test_cases', return_value=self.cases):
            return self.client.post(
                '/api/ai/submissions/',
                {'problem_id': self.problem.problem_id, 'code': code},
                format='json', **headers,
            )

    def test_run_enqueues_and_returns_202_without_result_or_secrets(self):
        response = self.post_run()
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data['status'], 'queued')
        self.assertTrue(response.data['created'])
        task = ExecutionTask.objects.get(public_id=response.data['task_id'])
        self.assertEqual(task.code, 'print(1)')
        self.assertEqual(task.task_type, TASK_TYPE_RUN)
        self.assertNotIn('code', response.data)
        self.assertNotIn('test_snapshot', response.data)
        self.assertNotIn('lease_token_hash', response.data)

    def test_grade_atomically_creates_pending_submission_and_snapshot(self):
        response = self.post_grade()
        self.assertEqual(response.status_code, 202)
        task = ExecutionTask.objects.get(public_id=response.data['task_id'])
        submission = Submission.objects.get(pk=response.data['submission_id'])
        self.assertEqual(task.task_type, TASK_TYPE_GRADE)
        self.assertEqual(task.test_snapshot['cases'][0]['number'], 1)
        self.assertEqual(task.test_snapshot['cases'][0]['output'], '2')
        self.assertIsNone(submission.score)
        self.assertEqual(submission.status, 'pending')
        self.assertEqual(submission.execution_task, task)
        self.assertNotIn('test_snapshot', response.data)

    def test_snapshot_does_not_change_when_problem_tests_change(self):
        response = self.post_grade()
        task = ExecutionTask.objects.get(public_id=response.data['task_id'])
        original_snapshot = task.test_snapshot
        self.cases[0]['output'] = '999'
        task.refresh_from_db()
        self.assertEqual(task.test_snapshot, original_snapshot)
        self.assertEqual(task.test_snapshot['cases'][0]['output'], '2')

    def test_same_idempotency_key_returns_same_run_task(self):
        key = str(uuid.uuid4())
        first = self.post_run(key=key)
        second = self.post_run(key=key)
        self.assertEqual(first.data['task_id'], second.data['task_id'])
        self.assertFalse(second.data['created'])
        self.assertEqual(ExecutionTask.objects.count(), 1)

    def test_same_idempotency_key_returns_same_submission(self):
        key = str(uuid.uuid4())
        first = self.post_grade(key=key)
        second = self.post_grade(key=key)
        self.assertEqual(first.data['task_id'], second.data['task_id'])
        self.assertEqual(first.data['submission_id'], second.data['submission_id'])
        self.assertEqual(ExecutionTask.objects.count(), 1)
        self.assertEqual(Submission.objects.count(), 1)

    def test_idempotency_key_reuse_with_different_payload_is_conflict(self):
        key = str(uuid.uuid4())
        self.assertEqual(self.post_run(code='print(1)', key=key).status_code, 202)
        response = self.post_run(code='print(2)', key=key)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'idempotency_conflict')

    @override_settings(EXECUTION_USER_QUEUED_LIMIT=2)
    def test_per_user_queue_limit(self):
        self.assertEqual(self.post_run(code='print(1)').status_code, 202)
        self.assertEqual(self.post_run(code='print(2)').status_code, 202)
        response = self.post_run(code='print(3)')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data['code'], 'queue_limit_reached')

    @override_settings(EXECUTION_USER_RUNNING_LIMIT=1)
    def test_per_user_running_limit(self):
        first = self.post_run()
        ExecutionTask.objects.filter(public_id=first.data['task_id']).update(status=STATUS_RUNNING)
        response = self.post_run(code='print(2)')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data['code'], 'running_limit_reached')

    def test_invalid_snapshot_leaves_no_partial_records(self):
        with patch.object(Problem, 'get_test_cases', return_value=[]):
            response = self.client.post(
                '/api/ai/submissions/',
                {'problem_id': self.problem.problem_id, 'code': 'print(1)'},
                format='json',
            )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(ExecutionTask.objects.count(), 0)
        self.assertEqual(Submission.objects.count(), 0)

    @override_settings(EXECUTION_CODE_MAX_BYTES=4)
    def test_code_size_limit_uses_utf8_bytes(self):
        response = self.post_run(code='你好')
        self.assertEqual(response.status_code, 413)
        self.assertEqual(ExecutionTask.objects.count(), 0)

    def test_active_endpoint_returns_latest_matching_task(self):
        response = self.post_grade()
        active = self.client.get(
            f'/api/ai/executions/active/?task_type=grade&problem_id={self.problem.problem_id}'
        )
        self.assertEqual(active.status_code, 200)
        self.assertEqual(active.data['task_id'], response.data['task_id'])

    def test_active_endpoint_returns_204_when_none_exists(self):
        response = self.client.get('/api/ai/executions/active/?task_type=run')
        self.assertEqual(response.status_code, 204)

    def test_task_detail_is_owner_scoped(self):
        task = ExecutionTask.objects.create(
            user=self.other_student, task_type=TASK_TYPE_RUN, code='secret code',
            snapshot_hash='a' * 64, limits={}, idempotency_key=str(uuid.uuid4()),
            expires_at='2099-01-01T00:00:00Z',
        )
        response = self.client.get(f'/api/ai/executions/{task.public_id}/')
        self.assertEqual(response.status_code, 404)

    def test_completed_detail_only_exposes_safe_result_fields(self):
        queued = self.post_run()
        task = ExecutionTask.objects.get(public_id=queued.data['task_id'])
        task.status = STATUS_SUCCEEDED
        task.stdout = 'ok\n'
        task.result_detail = {'termination_reason': 'completed'}
        task.lease_token_hash = 'do-not-leak'
        task.save()
        response = self.client.get(f'/api/ai/executions/{task.public_id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['output'], 'ok\n')
        self.assertNotIn('code', response.data)
        self.assertNotIn('limits', response.data)
        self.assertNotIn('lease_token_hash', response.data)

    def test_teacher_cannot_create_student_execution_task(self):
        teacher = CustomUser.objects.create_user(
            username='queue_teacher', password='test-pass', role='teacher',
        )
        token = Token.objects.create(user=teacher)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        response = self.post_run()
        self.assertEqual(response.status_code, 403)

    @override_settings(CODE_EXECUTION_ENABLED=False)
    def test_disabled_service_creates_nothing(self):
        response = self.post_run()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(ExecutionTask.objects.count(), 0)
