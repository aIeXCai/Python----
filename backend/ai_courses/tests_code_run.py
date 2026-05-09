"""
Code execution tests for ai_courses
Tests for:
  - utils.run_code_interactive()
  - views.CodeRunView (POST /api/ai/run_code/)
  - CodeRunRateThrottle (rate limiting)
  - urls (endpoint registration)

Run: cd backend && python manage.py test ai_courses.tests_code_run
"""
import json
import time
import subprocess
from unittest.mock import patch, MagicMock
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase
from rest_framework.authtoken.models import Token
from users.models import CustomUser
from .utils import run_code_interactive


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

class RunCodeInteractiveTest(TestCase):
    """Unit tests for run_code_interactive utility function."""

    def test_simple_print_output(self):
        """print('hello') returns output 'hello\n' with no error."""
        result = run_code_interactive("print('hello')", "")
        self.assertEqual(result['output'], 'hello\n')
        self.assertEqual(result['error'], '')
        self.assertFalse(result['timed_out'])
        self.assertGreater(result['execution_time'], 0)

    def test_with_stdin_input(self):
        """Code reading from stdin receives the passed input."""
        code = "data = input(); print('got:', data)"
        result = run_code_interactive(code, "hello_world")
        self.assertIn('hello_world', result['output'])
        self.assertEqual(result['error'], '')

    def test_runtime_error_zero_division(self):
        """x = 1/0 raises ZeroDivisionError captured in error field."""
        result = run_code_interactive("x = 1/0", "")
        self.assertIn('ZeroDivisionError', result['error'])
        self.assertFalse(result['timed_out'])

    def test_syntax_error(self):
        """Syntax error code produces SyntaxError in error field."""
        result = run_code_interactive("print('hello'", "")
        self.assertIn('SyntaxError', result['error'])
        self.assertFalse(result['timed_out'])

    def test_timeout_mocked(self):
        """subprocess.TimeoutExpired maps to timed_out=True with error message."""
        with patch('ai_courses.utils.subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd='python', timeout=10
            )
            result = run_code_interactive("while True: pass", "")
            self.assertTrue(result['timed_out'])
            self.assertIn('timed out', result['error'])
            self.assertIn('10 seconds', result['error'])

    def test_unexpected_exception_captured(self):
        """OSError from subprocess triggers generic execution error."""
        with patch('ai_courses.utils.subprocess.run') as mock_run:
            mock_run.side_effect = OSError("No such file")
            result = run_code_interactive("print('x')", "")
            self.assertIn('Execution error', result['error'])
            self.assertIn('No such file', result['error'])
            self.assertFalse(result['timed_out'])

    def test_result_has_all_expected_keys(self):
        """Returned dict contains output, error, execution_time, timed_out."""
        result = run_code_interactive("pass", "")
        for key in ('output', 'error', 'execution_time', 'timed_out'):
            self.assertIn(key, result)

    def test_execution_time_is_positive_float(self):
        """execution_time is a non-negative number."""
        result = run_code_interactive("print('test')", "")
        self.assertIsInstance(result['execution_time'], (int, float))
        self.assertGreaterEqual(result['execution_time'], 0)

    def test_temp_file_is_cleaned_up(self):
        """Temp Python file is removed via os.unlink after execution."""
        with patch('ai_courses.utils.os.unlink') as mock_unlink:
            run_code_interactive("print('x')", "")
            mock_unlink.assert_called_once()

    def test_temp_file_cleaned_up_even_on_error(self):
        """Temp file is removed even if subprocess raises an error."""
        with patch('ai_courses.utils.os.unlink') as mock_unlink:
            with patch('ai_courses.utils.subprocess.run') as mock_run:
                mock_run.side_effect = OSError("Some error")
                run_code_interactive("broken", "")
                mock_unlink.assert_called_once()


# ─── views.py: CodeRunView (POST /api/ai/run_code/) ────────────────────

class CodeRunViewBasicTest(APITestCase):
    """Basic functional tests for CodeRunView endpoint."""

    def setUp(self):
        cache.clear()  # Reset throttle counters between tests
        self.student = _make_student()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {_token(self.student)}')

    def test_run_code_200_success(self):
        """POST valid code returns 200 with output."""
        resp = self.client.post('/api/ai/run_code/', {
            'code': "print('hello')",
            'stdin': '',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('output', resp.data)
        self.assertEqual(resp.data['output'], 'hello\n')
        self.assertIn('error', resp.data)
        self.assertIn('execution_time', resp.data)

    def test_run_code_with_stdin(self):
        """POST with stdin field passes input to code."""
        code = "import sys; data = sys.stdin.read(); print('got:' + data.strip())"
        resp = self.client.post('/api/ai/run_code/', {
            'code': code,
            'stdin': 'my_input',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('got:my_input', resp.data['output'])

    def test_run_code_runtime_error_200(self):
        """POST code that raises runtime error still returns 200 with error info."""
        resp = self.client.post('/api/ai/run_code/', {
            'code': 'x = 1 / 0',
            'stdin': '',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('ZeroDivisionError', resp.data['error'])

    def test_run_code_timeout_408(self):
        """POST infinite loop returns 408 when run_code_interactive reports timed_out."""
        with patch('ai_courses.views.run_code_interactive') as mock_run:
            mock_run.return_value = {
                'output': '',
                'error': 'Code execution timed out after 10 seconds',
                'execution_time': 10.0,
                'timed_out': True,
            }
            resp = self.client.post('/api/ai/run_code/', {
                'code': 'while True: pass',
                'stdin': '',
            }, format='json')
            self.assertEqual(resp.status_code, 408)
            self.assertIn('timed out', resp.data['error'])

    def test_run_code_success_200_when_not_timed_out(self):
        """Normal execution (timed_out=False) returns 200 even with non-empty error."""
        with patch('ai_courses.views.run_code_interactive') as mock_run:
            mock_run.return_value = {
                'output': '',
                'error': 'Some non-fatal warning',
                'execution_time': 0.01,
                'timed_out': False,
            }
            resp = self.client.post('/api/ai/run_code/', {
                'code': 'print("ok")',
                'stdin': '',
            }, format='json')
            self.assertEqual(resp.status_code, 200)


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
        self.assertIn('code is required', resp.data['error'])

    def test_whitespace_only_code_400(self):
        """POST with whitespace-only code returns 400."""
        resp = self.client.post('/api/ai/run_code/', {
            'code': '   \n\t  ',
            'stdin': '',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('code is required', resp.data['error'])

    def test_missing_code_field_400(self):
        """POST without code field returns 400."""
        resp = self.client.post('/api/ai/run_code/', {
            'stdin': '',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('code is required', resp.data['error'])

    def test_unauthenticated_401(self):
        """POST without Authorization header returns 401."""
        self.client.credentials()  # clear auth
        resp = self.client.post('/api/ai/run_code/', {
            'code': "print('hello')",
            'stdin': '',
        }, format='json')
        self.assertEqual(resp.status_code, 401)


class CodeRunViewRateLimitTest(APITestCase):
    """Rate limiting tests for CodeRunView."""

    def setUp(self):
        cache.clear()  # Reset throttle counters between tests
        self.student = _make_student()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {_token(self.student)}')

    def test_rate_limit_3_per_second_exceeded_returns_429(self):
        """More than 3 requests within 1 second triggers 429."""
        # Mock run_code_interactive to avoid real Python execution overhead
        with patch('ai_courses.views.run_code_interactive') as mock_run:
            mock_run.return_value = {
                'output': '',
                'error': '',
                'execution_time': 0.0,
                'timed_out': False,
            }

            responses = []
            for i in range(5):
                resp = self.client.post('/api/ai/run_code/', {
                    'code': f"print({i})",
                    'stdin': '',
                }, format='json')
                responses.append(resp)

        statuses = [r.status_code for r in responses]
        # First 3 should be 200, 4th+ should be 429
        self.assertEqual(statuses[:3], [200, 200, 200],
                         f"First 3 should be 200, got {statuses[:3]}")
        self.assertIn(429, statuses[3:],
                      f"Requests 4+ should include 429, got {statuses[3:]}")

    def test_different_users_have_separate_rate_limits(self):
        """User A hitting the rate limit does not affect User B."""
        student2 = _make_student()
        student2_token = _token(student2)

        with patch('ai_courses.views.run_code_interactive') as mock_run:
            mock_run.return_value = {
                'output': '', 'error': '',
                'execution_time': 0.0, 'timed_out': False,
            }

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
            self.assertEqual(resp.status_code, 200,
                             "Different user should not be throttled")


class CodeRunViewResponseFormatTest(APITestCase):
    """Ensure response format matches the acceptance criteria exactly."""

    def setUp(self):
        cache.clear()  # Reset throttle counters between tests
        self.student = _make_student()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {_token(self.student)}')

    def test_response_structure_matches_spec(self):
        """Response contains output, error, execution_time as top-level keys."""
        resp = self.client.post('/api/ai/run_code/', {
            'code': "print('hello')",
            'stdin': '',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        self.assertIsInstance(data['output'], str)
        self.assertIsInstance(data['error'], str)
        self.assertIsInstance(data['execution_time'], (int, float))

    def test_execution_time_is_reasonable(self):
        """execution_time is non-negative and within reasonable bounds."""
        resp = self.client.post('/api/ai/run_code/', {
            'code': "print('hello')",
            'stdin': '',
        }, format='json')
        self.assertGreaterEqual(resp.data['execution_time'], 0)
        # Should not take more than 5 seconds for simple code
        self.assertLess(resp.data['execution_time'], 5.0)


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
