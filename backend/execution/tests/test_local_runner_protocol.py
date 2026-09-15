import sys
import uuid
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from execution.models import ExecutionTask
from ai_courses.models import Problem, Submission
from users.models import CustomUser


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from runner.api_client import RunnerApiClient  # noqa: E402
from runner.config import RunnerConfig  # noqa: E402
from runner.controller import LocalRunnerController  # noqa: E402


TEST_SECRET = 'local-runner-integration-secret-at-least-32-characters'


class _DjangoResponse:
    def __init__(self, response):
        self.status_code = response.status_code
        self.response = response

    def json(self):
        return self.response.data


class _DjangoSession:
    def __init__(self, client):
        self.client = client

    def post(self, url, *, data, headers, timeout):
        del timeout
        path = urlsplit(url).path
        response = self.client.generic(
            'POST', path, data, content_type='application/json', headers=headers,
        )
        return _DjangoResponse(response)


@override_settings(
    RUNNER_SERVICE_SECRET=TEST_SECRET,
    RUNNER_PROTOCOL_VERSION='runner.v1',
    CODE_EXECUTION_ENABLED=True,
)
class LocalRunnerProtocolIntegrationTest(APITestCase):
    def setUp(self):
        self.student = CustomUser.objects.create_user(
            username='local_runner_protocol_student', password='test-pass', role='student',
            grade='七年级', class_num='1', student_number='01',
        )
        self.config = RunnerConfig.from_mapping({
            'RUNNER_SERVICE_SECRET': TEST_SECRET,
            'RUNNER_PYTHON_EXECUTABLE': sys.executable,
            'RUNNER_ID': 'integration-local-runner',
        })
        self.client_impl = RunnerApiClient(
            self.config,
            session=_DjangoSession(APIClient()),
            clock=lambda: timezone.now().timestamp(),
            sleeper=lambda _seconds: None,
        )

    def test_real_client_registers_claims_renews_and_completes(self):
        heartbeat = self.client_impl.node_heartbeat(active_slots=0)
        self.assertEqual(heartbeat['runner_id'], 'integration-local-runner')

        task = ExecutionTask.objects.create(
            user=self.student,
            task_type='run',
            code='print("协议打通")',
            stdin='',
            snapshot_hash='a' * 64,
            limits={'wall_seconds': 10, 'task_wall_seconds': 12},
            idempotency_key=str(uuid.uuid4()),
            expires_at=timezone.now() + timedelta(minutes=2),
        )
        envelope = self.client_impl.claim_task()
        self.assertEqual(envelope['task_id'], str(task.public_id))
        self.assertEqual(envelope['code'], 'print("协议打通")')

        renewed = self.client_impl.task_heartbeat(
            envelope['task_id'], envelope['lease_token'],
        )
        self.assertEqual(renewed['task_id'], str(task.public_id))

        completed = self.client_impl.complete_task(
            envelope['task_id'], envelope['lease_token'], {
                'status': 'succeeded',
                'stdout': '协议打通\n',
                'stderr': '',
                'execution_ms': 5,
                'detail': {'termination_reason': 'completed', 'output_truncated': False},
            },
        )
        self.assertTrue(completed['applied'])
        task.refresh_from_db()
        self.assertEqual(task.status, 'succeeded')
        self.assertEqual(task.stdout, '协议打通\n')

    def test_controller_executes_and_grades_through_real_web_contract(self):
        self.client_impl.node_heartbeat(active_slots=0)
        problem = Problem.objects.create(problem_id='local_runner_grade', course='ai')
        task = ExecutionTask.objects.create(
            user=self.student,
            problem=problem,
            task_type='grade',
            code='print(int(input()) * 2)',
            stdin='',
            test_snapshot={
                'schema_version': 1,
                'problem_id': problem.problem_id,
                'cases': [
                    {'number': 1, 'input': '2\n', 'output': '4'},
                    {'number': 2, 'input': '5\n', 'output': '10'},
                ],
            },
            snapshot_hash='b' * 64,
            limits={
                'memory_mb': 128, 'pids': 16, 'output_bytes': 131072,
                'case_wall_seconds': 5, 'task_wall_seconds': 30,
            },
            idempotency_key=str(uuid.uuid4()),
            expires_at=timezone.now() + timedelta(minutes=2),
        )
        submission = Submission.objects.create(
            user=self.student,
            problem=problem,
            code=task.code,
            score=None,
            status='pending',
            execution_task=task,
        )
        envelope = self.client_impl.claim_task()
        controller = LocalRunnerController(self.config, api_client=self.client_impl)
        controller.process_task(envelope)

        task.refresh_from_db()
        submission.refresh_from_db()
        self.assertEqual(task.status, 'succeeded')
        self.assertEqual(task.score, 100)
        self.assertEqual(submission.status, 'accepted')
        self.assertEqual(submission.score, 100)
        self.assertEqual(
            [item['status'] for item in task.result_detail['tests']],
            ['passed', 'passed'],
        )
