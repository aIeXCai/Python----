import os
import sys
import unittest

from runner.config import RunnerConfig, RunnerConfigError


SECRET = 'runner-test-secret-that-is-long-enough-123456'


def values(**overrides):
    result = {
        'RUNNER_SERVICE_SECRET': SECRET,
        'RUNNER_PYTHON_EXECUTABLE': sys.executable,
    }
    result.update(overrides)
    return result


class RunnerConfigTest(unittest.TestCase):
    def test_defaults_are_local_and_cross_platform(self):
        config = RunnerConfig.from_mapping(values())
        self.assertEqual(config.web_internal_url, 'http://127.0.0.1:8080')
        self.assertEqual(config.concurrency, 2)
        self.assertEqual(config.python_executable, os.path.realpath(sys.executable))

    def test_rejects_missing_or_placeholder_secret(self):
        for secret in ('', 'short', 'replace-with-an-independent-runner-secret'):
            with self.subTest(secret=secret):
                with self.assertRaises(RunnerConfigError):
                    RunnerConfig.from_mapping(values(RUNNER_SERVICE_SECRET=secret))

    def test_rejects_remote_web_without_explicit_opt_in(self):
        with self.assertRaisesRegex(RunnerConfigError, 'RUNNER_ALLOW_REMOTE_WEB'):
            RunnerConfig.from_mapping(values(RUNNER_WEB_INTERNAL_URL='http://10.0.0.8:8080'))
        config = RunnerConfig.from_mapping(values(
            RUNNER_WEB_INTERNAL_URL='http://10.0.0.8:8080/',
            RUNNER_ALLOW_REMOTE_WEB='true',
        ))
        self.assertEqual(config.web_internal_url, 'http://10.0.0.8:8080')

    def test_rejects_invalid_ranges_and_python_path(self):
        for override in (
            {'RUNNER_CONCURRENCY': '0'},
            {'RUNNER_CONCURRENCY': 'many'},
            {'RUNNER_MAX_MEMORY_MB': '8'},
            {'RUNNER_MAX_PIDS': '0'},
            {'RUNNER_PYTHON_EXECUTABLE': '/definitely/missing/python'},
        ):
            with self.subTest(override=override):
                with self.assertRaises(RunnerConfigError):
                    RunnerConfig.from_mapping(values(**override))


if __name__ == '__main__':
    unittest.main()
