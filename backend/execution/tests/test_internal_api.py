import json
import time
import uuid
from datetime import timedelta

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from ai_courses.models import Problem, Submission
from execution.constants import (
    STATUS_CANCELLED,
    STATUS_QUEUED,
    STATUS_RUNNING,
    STATUS_SUCCEEDED,
    STATUS_SYSTEM_ERROR,
    STATUS_WRONG_ANSWER,
    TASK_TYPE_GRADE,
    TASK_TYPE_RUN,
)
from execution.internal_auth import sign_runner_request
from execution.models import ExecutionTask, RunnerNode, RunnerRequestReceipt
from execution.queue import recover_expired_tasks
from users.models import CustomUser


TEST_RUNNER_SECRET = 'stage5-test-runner-secret-at-least-32-characters'


@override_settings(
    RUNNER_SERVICE_SECRET=TEST_RUNNER_SECRET,
    RUNNER_PROTOCOL_VERSION='runner.v1',
    CODE_EXECUTION_ENABLED=True,
    EXECUTION_LEASE_SECONDS=30,
    EXECUTION_MAX_ATTEMPTS=2,
)
class RunnerInternalApiTest(APITestCase):
    runner_id = 'test-runner-1'

    def setUp(self):
        self.student = CustomUser.objects.create_user(
            username='internal_runner_student', password='test-pass', role='student',
            grade='七年级', class_num='1', student_number='01',
        )
        self.other_student = CustomUser.objects.create_user(
            username='internal_runner_student_2', password='test-pass', role='student',
            grade='七年级', class_num='1', student_number='02',
        )
        self.problem = Problem.objects.create(problem_id='internal_problem', course='ai')
        RunnerNode.objects.create(
            runner_id=self.runner_id,
            protocol_version='runner.v1',
            sandbox_image_digest='sha256:' + ('a' * 64),
            capacity=2,
            active_slots=0,
            status='online',
            last_heartbeat_at=timezone.now(),
        )

    def make_task(self, *, user=None, task_type=TASK_TYPE_RUN, status=STATUS_QUEUED, **overrides):
        values = {
            'user': user or self.student,
            'problem': self.problem if task_type == TASK_TYPE_GRADE else None,
            'task_type': task_type,
            'status': status,
            'code': 'print(1)',
            'stdin': '',
            'test_snapshot': (
                {'schema_version': 1, 'problem_id': self.problem.problem_id,
                 'cases': [{'number': 1, 'input': '', 'output': '1'}]}
                if task_type == TASK_TYPE_GRADE else None
            ),
            'snapshot_hash': 'a' * 64,
            'limits': {'wall_seconds': 10},
            'idempotency_key': str(uuid.uuid4()),
            'expires_at': timezone.now() + timedelta(minutes=2),
        }
        values.update(overrides)
        task = ExecutionTask.objects.create(**values)
        if task_type == TASK_TYPE_GRADE:
            Submission.objects.create(
                user=values['user'], problem=self.problem, code=values['code'],
                score=None, status='pending', execution_task=task,
            )
        return task

    def signed_post(self, path, payload, *, request_id=None, timestamp=None, secret=TEST_RUNNER_SECRET):
        body = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        request_id = request_id or uuid.uuid4()
        timestamp = int(time.time()) if timestamp is None else timestamp
        signature = sign_runner_request(
            secret=secret, method='POST', path=path, timestamp=timestamp,
            request_id=request_id, body=body,
        )
        return self.client.generic(
            'POST', path, body, content_type='application/json',
            HTTP_X_RUNNER_ID=self.runner_id,
            HTTP_X_RUNNER_TIMESTAMP=str(timestamp),
            HTTP_X_RUNNER_REQUEST_ID=str(request_id),
            HTTP_X_RUNNER_SIGNATURE=f'sha256={signature}',
        )

    def claim(self, **kwargs):
        return self.signed_post(
            '/internal/runner/v1/tasks/claim',
            {'protocol_version': 'runner.v1'},
            **kwargs,
        )

    def test_missing_invalid_and_stale_signatures_are_rejected(self):
        missing = self.client.post(
            '/internal/runner/v1/tasks/claim',
            {'protocol_version': 'runner.v1'}, format='json',
        )
        invalid = self.signed_post(
            '/internal/runner/v1/tasks/claim',
            {'protocol_version': 'runner.v1'}, secret='wrong-secret-that-is-also-long-enough-000',
        )
        stale = self.signed_post(
            '/internal/runner/v1/tasks/claim',
            {'protocol_version': 'runner.v1'}, timestamp=int(time.time()) - 120,
        )
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(invalid.status_code, 401)
        self.assertEqual(stale.status_code, 401)
        self.assertEqual(RunnerRequestReceipt.objects.count(), 0)

    def test_protocol_mismatch_is_rejected_before_claim(self):
        self.make_task()
        response = self.signed_post(
            '/internal/runner/v1/tasks/claim',
            {'protocol_version': 'runner.v2'},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(ExecutionTask.objects.get().status, STATUS_QUEUED)

    def test_unregistered_runner_cannot_claim(self):
        RunnerNode.objects.filter(runner_id=self.runner_id).delete()
        self.make_task()
        response = self.claim()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['code'], 'runner_not_registered')

    def test_runner_cannot_claim_past_registered_capacity(self):
        RunnerNode.objects.filter(runner_id=self.runner_id).update(capacity=1)
        self.make_task(
            status=STATUS_RUNNING,
            leased_by=self.runner_id,
            lease_token_hash='a' * 64,
            lease_expires_at=timezone.now() + timedelta(seconds=20),
        )
        queued = self.make_task(user=self.other_student)
        response = self.claim()
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data['task'])
        queued.refresh_from_db()
        self.assertEqual(queued.status, STATUS_QUEUED)

    def test_claim_returns_private_envelope_and_starts_submission(self):
        task = self.make_task(task_type=TASK_TYPE_GRADE)
        response = self.claim()
        self.assertEqual(response.status_code, 200)
        envelope = response.data['task']
        self.assertEqual(envelope['task_id'], str(task.public_id))
        self.assertEqual(envelope['code'], 'print(1)')
        self.assertEqual(envelope['test_snapshot']['cases'][0]['output'], '1')
        self.assertGreaterEqual(len(envelope['lease_token']), 32)
        task.refresh_from_db()
        task.submission.refresh_from_db()
        self.assertEqual(task.status, STATUS_RUNNING)
        self.assertEqual(task.attempt_count, 1)
        self.assertEqual(task.submission.status, 'running')

    def test_claim_request_replay_is_rejected_and_never_claims_twice(self):
        first_task = self.make_task()
        second_task = self.make_task(user=self.other_student)
        request_id = uuid.uuid4()
        first = self.claim(request_id=request_id)
        replay = self.claim(request_id=request_id)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(replay.status_code, 409)
        self.assertEqual(replay.data['code'], 'request_already_processed')
        self.assertEqual(ExecutionTask.objects.filter(status=STATUS_RUNNING).count(), 1)
        receipt = RunnerRequestReceipt.objects.get(request_id=request_id)
        self.assertIsNone(receipt.response_body)
        second_task.refresh_from_db()
        self.assertEqual(second_task.status, STATUS_QUEUED)

    def test_claim_skips_second_task_for_user_already_running(self):
        self.make_task(status=STATUS_RUNNING, leased_by='another-runner',
                       lease_token_hash='b' * 64,
                       lease_expires_at=timezone.now() + timedelta(seconds=20))
        same_user_queued = self.make_task()
        other_user_queued = self.make_task(user=self.other_student)
        response = self.claim()
        self.assertEqual(response.data['task']['task_id'], str(other_user_queued.public_id))
        same_user_queued.refresh_from_db()
        self.assertEqual(same_user_queued.status, STATUS_QUEUED)

    def test_heartbeat_extends_valid_lease_and_rejects_wrong_token(self):
        task = self.make_task()
        claim = self.claim().data['task']
        original_expiry = ExecutionTask.objects.get(pk=task.pk).lease_expires_at
        path = f'/internal/runner/v1/tasks/{task.public_id}/heartbeat'
        response = self.signed_post(path, {
            'protocol_version': 'runner.v1', 'lease_token': claim['lease_token'],
        })
        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertGreaterEqual(task.lease_expires_at, original_expiry)
        wrong = self.signed_post(path, {
            'protocol_version': 'runner.v1', 'lease_token': 'x' * 40,
        })
        self.assertEqual(wrong.status_code, 403)

    def test_run_completion_is_idempotent_and_updates_safe_result(self):
        task = self.make_task()
        lease = self.claim().data['task']['lease_token']
        path = f'/internal/runner/v1/tasks/{task.public_id}/complete'
        payload = {
            'protocol_version': 'runner.v1', 'lease_token': lease,
            'status': STATUS_SUCCEEDED, 'stdout': '1\n', 'stderr': '',
            'execution_ms': 12,
            'detail': {'termination_reason': 'completed', 'untrusted': 'discard me'},
        }
        first = self.signed_post(path, payload)
        duplicate = self.signed_post(path, payload)
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.data['applied'])
        self.assertEqual(duplicate.status_code, 200)
        self.assertFalse(duplicate.data['applied'])
        task.refresh_from_db()
        self.assertEqual(task.status, STATUS_SUCCEEDED)
        self.assertEqual(task.stdout, '1\n')
        self.assertNotIn('untrusted', task.result_detail)

    def test_grade_completion_atomically_updates_submission_and_uses_snapshot_expected(self):
        task = self.make_task(task_type=TASK_TYPE_GRADE)
        lease = self.claim().data['task']['lease_token']
        path = f'/internal/runner/v1/tasks/{task.public_id}/complete'
        response = self.signed_post(path, {
            'protocol_version': 'runner.v1', 'lease_token': lease,
            'status': STATUS_WRONG_ANSWER, 'stdout': '', 'stderr': '',
            'execution_ms': 18, 'score': 0,
            'detail': {'tests': [{
                'number': 1, 'status': 'wrong_answer', 'actual_output': '9',
                'expected_output': 'forged', 'stderr': '', 'execution_ms': 18,
            }]},
        })
        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        task.submission.refresh_from_db()
        self.assertEqual(task.status, STATUS_WRONG_ANSWER)
        self.assertEqual(task.score, 0)
        self.assertEqual(task.submission.status, 'wrong_answer')
        self.assertEqual(task.submission.score, 0)
        self.assertEqual(task.result_detail['tests'][0]['expected_output'], '1')

    def test_invalid_completion_does_not_mutate_task_or_submission(self):
        task = self.make_task(task_type=TASK_TYPE_GRADE)
        lease = self.claim().data['task']['lease_token']
        path = f'/internal/runner/v1/tasks/{task.public_id}/complete'
        response = self.signed_post(path, {
            'protocol_version': 'runner.v1', 'lease_token': lease,
            'status': STATUS_SUCCEEDED, 'stdout': '', 'stderr': '',
            'execution_ms': 1, 'score': 50, 'detail': {'tests': []},
        })
        self.assertEqual(response.status_code, 400)
        task.refresh_from_db()
        task.submission.refresh_from_db()
        self.assertEqual(task.status, STATUS_RUNNING)
        self.assertEqual(task.submission.status, 'running')
        self.assertIsNone(task.submission.score)

    def test_system_error_never_creates_zero_score(self):
        task = self.make_task(task_type=TASK_TYPE_GRADE)
        lease = self.claim().data['task']['lease_token']
        path = f'/internal/runner/v1/tasks/{task.public_id}/complete'
        response = self.signed_post(path, {
            'protocol_version': 'runner.v1', 'lease_token': lease,
            'status': STATUS_SYSTEM_ERROR, 'stdout': '', 'stderr': 'runner failed',
            'execution_ms': 1, 'score': None, 'detail': {},
        })
        self.assertEqual(response.status_code, 200)
        task.submission.refresh_from_db()
        self.assertIsNone(task.submission.score)
        self.assertEqual(task.submission.status, 'error')

    def test_node_heartbeat_upserts_health_without_secret(self):
        path = '/internal/runner/v1/nodes/heartbeat'
        response = self.signed_post(path, {
            'protocol_version': 'runner.v1',
            'sandbox_image_digest': 'sha256:' + ('c' * 64),
            'capacity': 2, 'active_slots': 1, 'status': 'online',
        })
        self.assertEqual(response.status_code, 200)
        node = RunnerNode.objects.get(runner_id=self.runner_id)
        self.assertEqual(node.active_slots, 1)

    def test_execution_disabled_prevents_claim(self):
        self.make_task()
        with override_settings(CODE_EXECUTION_ENABLED=False):
            response = self.claim()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(ExecutionTask.objects.get().status, STATUS_QUEUED)


@override_settings(EXECUTION_MAX_ATTEMPTS=2, EXECUTION_QUEUE_TTL_SECONDS=120)
class TaskRecoveryTest(APITestCase):
    def setUp(self):
        self.student = CustomUser.objects.create_user(
            username='recovery_student', password='test-pass', role='student',
            grade='七年级', class_num='1', student_number='01',
        )

    def make_task(self, **overrides):
        values = {
            'user': self.student, 'task_type': TASK_TYPE_RUN, 'code': 'pass',
            'snapshot_hash': 'd' * 64, 'limits': {},
            'idempotency_key': str(uuid.uuid4()),
            'expires_at': timezone.now() + timedelta(minutes=2),
        }
        values.update(overrides)
        return ExecutionTask.objects.create(**values)

    def test_expired_queued_task_is_cancelled(self):
        task = self.make_task(expires_at=timezone.now() - timedelta(seconds=1))
        result = recover_expired_tasks()
        task.refresh_from_db()
        self.assertEqual(result['cancelled'], 1)
        self.assertEqual(task.status, STATUS_CANCELLED)

    def test_first_expired_lease_requeues_and_clears_lease(self):
        task = self.make_task(
            status=STATUS_RUNNING, attempt_count=1, leased_by='lost-runner',
            lease_token_hash='e' * 64,
            lease_expires_at=timezone.now() - timedelta(seconds=1),
        )
        result = recover_expired_tasks()
        task.refresh_from_db()
        self.assertEqual(result['requeued'], 1)
        self.assertEqual(task.status, STATUS_QUEUED)
        self.assertEqual(task.leased_by, '')
        self.assertIsNone(task.lease_expires_at)

    def test_second_expired_lease_becomes_system_error(self):
        task = self.make_task(
            status=STATUS_RUNNING, attempt_count=2, leased_by='lost-runner',
            lease_token_hash='f' * 64,
            lease_expires_at=timezone.now() - timedelta(seconds=1),
        )
        result = recover_expired_tasks()
        task.refresh_from_db()
        self.assertEqual(result['failed'], 1)
        self.assertEqual(task.status, STATUS_SYSTEM_ERROR)
