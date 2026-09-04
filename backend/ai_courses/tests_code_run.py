"""
Code execution tests for ai_courses
Tests for:
  - views.CodeRunView (POST /api/ai/run_code/)
  - CodeRunRateThrottle (rate limiting)
  - urls (endpoint registration)
  - absence of legacy Web-process execution paths

Run: cd backend && python manage.py test ai_courses.tests_code_run
"""
from pathlib import Path
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase
from rest_framework.authtoken.models import Token
from users.models import CustomUser


# ─── Test helpers ────────────────────────────────────────────────────────

_counter = [0]


def _make_student():
    _counter[0] += 1
    return CustomUser.objects.create_user(
        username=f'code_run_stu_{_counter[0]}',
        password='test123', role='student',
        grade='七年级', class_num='1',
        student_number=f'{_counter[0]:02d}',
        display_name=f'测试学生{_counter[0]}'
    )


def _token(user):
    return Token.objects.get_or_create(user=user)[0].key


# ─── utils.py: run_code_interactive() ──────────────────────────────────

class NoLocalExecutionPathTest(TestCase):
    """Django business code must not contain a student-code subprocess path."""

    def test_legacy_executor_module_is_removed(self):
        app_dir = Path(__file__).resolve().parent
        self.assertFalse((app_dir / 'utils.py').exists())

    def test_ai_business_modules_do_not_invoke_subprocess(self):
        app_dir = Path(__file__).resolve().parent
        for filename in ('models.py', 'views.py'):
            source = (app_dir / filename).read_text(encoding='utf-8')
            self.assertNotIn('subprocess', source, filename)

# ─── views.py: CodeRunView (POST /api/ai/run_code/) ────────────────────

class CodeRunViewBasicTest(APITestCase):
    """Basic functional tests for CodeRunView endpoint."""

    def setUp(self):
        cache.clear()  # Reset throttle counters between tests
        self.student = _make_student()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {_token(self.student)}')

    def test_run_code_202_queued(self):
        """POST valid code creates an asynchronous task."""
        resp = self.client.post('/api/ai/run_code/', {
            'code': "print('hello')",
            'stdin': '',
        }, format='json')
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.data['status'], 'queued')
        self.assertIn('task_id', resp.data)
        self.assertNotIn('output', resp.data)

    def test_run_code_with_stdin(self):
        """POST stores stdin in the immutable task request."""
        code = "import sys; data = sys.stdin.read(); print('got:' + data.strip())"
        resp = self.client.post('/api/ai/run_code/', {
            'code': code,
            'stdin': 'my_input',
        }, format='json')
        self.assertEqual(resp.status_code, 202)
        from execution.models import ExecutionTask
        self.assertEqual(ExecutionTask.objects.get().stdin, 'my_input')

    def test_run_code_does_not_execute_runtime_error_in_web(self):
        resp = self.client.post('/api/ai/run_code/', {
            'code': 'x = 1 / 0',
            'stdin': '',
        }, format='json')
        self.assertEqual(resp.status_code, 202)
        self.assertNotIn('error', resp.data)

    def test_infinite_loop_is_only_queued_by_web(self):
        resp = self.client.post('/api/ai/run_code/', {
            'code': 'while True: pass',
            'stdin': '',
        }, format='json')
        self.assertEqual(resp.status_code, 202)

    def test_server_side_limits_are_snapshotted(self):
        resp = self.client.post('/api/ai/run_code/', {
            'code': 'print("ok")', 'stdin': '', 'wall_seconds': 999,
        }, format='json')
        self.assertEqual(resp.status_code, 202)
        from execution.models import ExecutionTask
        self.assertEqual(ExecutionTask.objects.get().limits['wall_seconds'], 10)


class CodeRunViewValidationTest(APITestCase):
    """Input validation tests for CodeRunView."""

    def setUp(self):
        cache.clear()  # Reset throttle counters between tests
        self.student = _make_student()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {_token(self.student)}')

    def test_empty_code_400(self):
        """POST with empty string code returns 400."""
        resp = self.client.post('/api/ai/run_code/', {
            'code': '',
            'stdin': '',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('code', resp.data['details'])

    def test_whitespace_only_code_400(self):
        """POST with whitespace-only code returns 400."""
        resp = self.client.post('/api/ai/run_code/', {
            'code': '   \n\t  ',
            'stdin': '',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('code', resp.data['details'])

    def test_missing_code_field_400(self):
        """POST without code field returns 400."""
        resp = self.client.post('/api/ai/run_code/', {
            'stdin': '',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('code', resp.data['details'])

    def test_unauthenticated_401(self):
        """POST without Authorization header returns 401."""
        self.client.credentials()  # clear auth
        resp = self.client.post('/api/ai/run_code/', {
            'code': "print('hello')",
            'stdin': '',
        }, format='json')
        self.assertEqual(resp.status_code, 401)

    @override_settings(CODE_EXECUTION_ENABLED=False)
    def test_disabled_execution_fails_closed_without_local_run(self):
        """Disabled execution returns 503 without creating a task."""
        resp = self.client.post('/api/ai/run_code/', {
            'code': "print('must not run')",
            'stdin': '',
        }, format='json')

        self.assertEqual(resp.status_code, 503)
        self.assertIn('暂不可用', resp.data['error'])
        from execution.models import ExecutionTask
        self.assertFalse(ExecutionTask.objects.exists())

    @override_settings(CODE_EXECUTION_ENABLED=False)
    def test_disabled_submission_fails_closed_without_local_grading(self):
        """Disabled grading returns 503 before a task or submission is created."""
        resp = self.client.post('/api/ai/submissions/', {
            'problem_id': 'does-not-matter',
            'code': "print('must not run')",
        }, format='json')

        self.assertEqual(resp.status_code, 503)
        self.assertIn('暂不可用', resp.data['error'])
        from execution.models import ExecutionTask
        from .models import Submission
        self.assertFalse(ExecutionTask.objects.exists())
        self.assertFalse(Submission.objects.exists())

    @override_settings(CODE_EXECUTION_ENABLED=True)
    def test_enabled_endpoint_only_queues_execution(self):
        """Enabled mode creates a durable task and does not execute in Django."""
        resp = self.client.post('/api/ai/run_code/', {
            'code': "print('must run only in Runner')",
            'stdin': '',
        }, format='json')

        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.data['status'], 'queued')


@override_settings(EXECUTION_USER_QUEUED_LIMIT=100)
class CodeRunViewRateLimitTest(APITestCase):
    """Rate limiting tests for CodeRunView."""

    def setUp(self):
        cache.clear()  # Reset throttle counters between tests
        self.student = _make_student()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {_token(self.student)}')

    def test_rate_limit_3_per_second_exceeded_returns_429(self):
        """More than 3 requests within 1 second triggers 429."""
        responses = []
        for i in range(5):
            resp = self.client.post('/api/ai/run_code/', {
                'code': f"print({i})",
                'stdin': '',
            }, format='json')
            responses.append(resp)

        statuses = [r.status_code for r in responses]
        # First 3 should be accepted, 4th+ should be throttled.
        self.assertEqual(statuses[:3], [202, 202, 202],
                         f"First 3 should be 202, got {statuses[:3]}")
        self.assertIn(429, statuses[3:],
                      f"Requests 4+ should include 429, got {statuses[3:]}")

    def test_different_users_have_separate_rate_limits(self):
        """User A hitting the rate limit does not affect User B."""
        student2 = _make_student()
        student2_token = _token(student2)

        # Student 1 exhausts rate limit (first 3 ok, 4th throttled)
        for _ in range(3):
            self.client.post('/api/ai/run_code/', {
                'code': "pass", 'stdin': '',
            }, format='json')

        # Student 2 should still be able to make requests
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {student2_token}')
        resp = self.client.post('/api/ai/run_code/', {
            'code': "pass", 'stdin': '',
        }, format='json')
        self.assertEqual(resp.status_code, 202,
                         "Different user should not be throttled")


class CodeRunViewResponseFormatTest(APITestCase):
    """Ensure response format matches the acceptance criteria exactly."""

    def setUp(self):
        cache.clear()  # Reset throttle counters between tests
        self.student = _make_student()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {_token(self.student)}')

    def test_response_structure_matches_spec(self):
        """Creation response contains the asynchronous task contract."""
        resp = self.client.post('/api/ai/run_code/', {
            'code': "print('hello')",
            'stdin': '',
        }, format='json')
        self.assertEqual(resp.status_code, 202)
        data = resp.data
        self.assertIsInstance(data['task_id'], str)
        self.assertEqual(data['status'], 'queued')
        self.assertIsInstance(data['poll_after_ms'], int)

    def test_creation_response_has_no_fake_execution_time(self):
        resp = self.client.post('/api/ai/run_code/', {
            'code': "print('hello')",
            'stdin': '',
        }, format='json')
        self.assertEqual(resp.status_code, 202)
        self.assertNotIn('execution_time', resp.data)


# ─── urls.py: endpoint registration ────────────────────────────────────

class CodeRunUrlRegistrationTest(TestCase):
    """Verify /api/ai/run_code/ is properly registered."""

    def test_run_code_url_resolves_to_code_run_view(self):
        """reverse('run-code') resolves to /api/ai/run_code/."""
        from django.urls import reverse
        url = reverse('run-code')
        self.assertEqual(url, '/api/ai/run_code/')

    def test_run_code_url_in_resolver(self):
        """The endpoint can be resolved from the URL path."""
        from django.urls import resolve
        resolver = resolve('/api/ai/run_code/')
        self.assertEqual(resolver.url_name, 'run-code')
        self.assertEqual(resolver.view_name, 'run-code')


# ─── Throttle class ─────────────────────────────────────────────────────

class CodeRunRateThrottleTest(TestCase):
    """Unit test for CodeRunRateThrottle configuration."""

    def test_throttle_rate_is_3_per_second(self):
        """CodeRunRateThrottle.rate equals '3/second'."""
        from ai_courses.views import CodeRunRateThrottle
        self.assertEqual(CodeRunRateThrottle.rate, '3/second')

    def test_throttle_is_user_rate_throttle(self):
        """CodeRunRateThrottle inherits from UserRateThrottle."""
        from rest_framework.throttling import UserRateThrottle
        from ai_courses.views import CodeRunRateThrottle
        self.assertTrue(
            issubclass(CodeRunRateThrottle, UserRateThrottle),
            "CodeRunRateThrottle must inherit from UserRateThrottle"
        )
