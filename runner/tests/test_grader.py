import sys
import tempfile
import unittest
from pathlib import Path

from runner.config import RunnerConfig
from runner.grader import TaskEvaluator
from runner.local_executor import LocalProcessExecutor


SECRET = 'runner-test-secret-that-is-long-enough-123456'


def config(**overrides):
    values = {
        'RUNNER_SERVICE_SECRET': SECRET,
        'RUNNER_PYTHON_EXECUTABLE': sys.executable,
        'RUNNER_MAX_MEMORY_MB': '128',
        'RUNNER_MAX_PIDS': '16',
        'RUNNER_MAX_OUTPUT_BYTES': '4096',
        'RUNNER_MAX_CASE_SECONDS': '2',
        'RUNNER_MAX_TASK_SECONDS': '5',
    }
    values.update(overrides)
    return RunnerConfig.from_mapping(values)


def grade_envelope(code, cases, **limit_overrides):
    limits = {
        'memory_mb': 128,
        'pids': 16,
        'output_bytes': 4096,
        'case_wall_seconds': 2,
        'task_wall_seconds': 5,
    }
    limits.update(limit_overrides)
    return {
        'task_type': 'grade',
        'code': code,
        'stdin': '',
        'test_snapshot': {'schema_version': 1, 'problem_id': 'p1', 'cases': cases},
        'limits': limits,
    }


class TaskEvaluatorTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.executor = LocalProcessExecutor(config(), temp_root=Path(self.temp.name))
        self.evaluator = TaskEvaluator(self.executor)

    def tearDown(self):
        self.executor.terminate_all()
        self.temp.cleanup()

    def test_run_returns_public_runner_payload(self):
        result = self.evaluator.evaluate({
            'task_type': 'run', 'code': 'print(input().upper())', 'stdin': 'hello\n',
            'limits': {'wall_seconds': 2, 'output_bytes': 4096},
        })
        self.assertEqual(result['status'], 'succeeded')
        self.assertEqual(result['stdout'], 'HELLO\n')
        self.assertEqual(result['detail']['termination_reason'], 'completed')

    def test_all_grade_cases_pass(self):
        result = self.evaluator.evaluate(grade_envelope(
            'print(int(input()) * 2)',
            [
                {'number': 1, 'input': '2\n', 'output': '4'},
                {'number': 2, 'input': '5\n', 'output': '10'},
            ],
        ))
        self.assertEqual(result['status'], 'succeeded')
        self.assertEqual(result['score'], 100)
        self.assertEqual([item['status'] for item in result['detail']['tests']], ['passed', 'passed'])

    def test_partial_wrong_answer_scores_by_total_cases(self):
        result = self.evaluator.evaluate(grade_envelope(
            'print(int(input()) * 2)',
            [
                {'number': 1, 'input': '2\n', 'output': '4'},
                {'number': 2, 'input': '5\n', 'output': '11'},
            ],
        ))
        self.assertEqual(result['status'], 'wrong_answer')
        self.assertEqual(result['score'], 50)
        self.assertNotIn('expected_output', result['detail']['tests'][1])

    def test_each_case_gets_a_fresh_directory(self):
        code = (
            'from pathlib import Path\n'
            'marker = Path("marker")\n'
            'print(marker.exists())\n'
            'marker.write_text("created")\n'
        )
        result = self.evaluator.evaluate(grade_envelope(code, [
            {'number': 1, 'input': '', 'output': 'False'},
            {'number': 2, 'input': '', 'output': 'False'},
        ]))
        self.assertEqual(result['status'], 'succeeded')

    def test_runtime_error_is_reported_per_case(self):
        result = self.evaluator.evaluate(grade_envelope(
            'raise RuntimeError("broken")',
            [{'number': 1, 'input': '', 'output': ''}],
        ))
        self.assertEqual(result['status'], 'runtime_error')
        self.assertEqual(result['score'], 0)
        self.assertEqual(result['detail']['tests'][0]['status'], 'runtime_error')
        self.assertIn('RuntimeError: broken', result['detail']['tests'][0]['stderr'])

    def test_case_timeout_stops_further_cases(self):
        result = self.evaluator.evaluate(grade_envelope(
            'while True: pass',
            [
                {'number': 1, 'input': '', 'output': ''},
                {'number': 2, 'input': '', 'output': ''},
            ],
            case_wall_seconds=0.1,
        ))
        self.assertEqual(result['status'], 'timed_out')
        self.assertEqual(result['score'], 0)
        self.assertEqual(len(result['detail']['tests']), 1)

    def test_output_budget_is_shared_across_cases(self):
        limited_executor = LocalProcessExecutor(
            config(RUNNER_MAX_OUTPUT_BYTES='1024'), temp_root=Path(self.temp.name),
        )
        evaluator = TaskEvaluator(limited_executor)
        result = evaluator.evaluate(grade_envelope(
            'print("x" * 799)',
            [
                {'number': 1, 'input': '', 'output': 'wrong'},
                {'number': 2, 'input': '', 'output': 'wrong'},
            ],
            output_bytes=1024,
        ))
        self.assertEqual(result['status'], 'resource_limited')
        self.assertEqual(result['detail']['termination_reason'], 'output_limit')
        total = sum(
            len(item['actual_output'].encode()) + len(item['stderr'].encode())
            for item in result['detail']['tests']
        )
        self.assertLessEqual(total, 1024)

    def test_invalid_snapshot_is_system_error_without_fake_score(self):
        result = self.evaluator.evaluate({
            'task_type': 'grade', 'code': 'print(1)',
            'test_snapshot': {'cases': []}, 'limits': {},
        })
        self.assertEqual(result['status'], 'system_error')
        self.assertIsNone(result['score'])
        self.assertEqual(result['detail']['termination_reason'], 'invalid_test_snapshot')


if __name__ == '__main__':
    unittest.main()
