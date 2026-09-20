import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

import psutil

from runner.config import RunnerConfig
from runner.local_executor import (
    LocalProcessExecutor,
    _platform_spawn_kwargs,
    _student_environment,
    _windows_taskkill_command,
)


SECRET = 'runner-test-secret-that-is-long-enough-123456'


def config(**overrides):
    values = {
        'RUNNER_SERVICE_SECRET': SECRET,
        'RUNNER_PYTHON_EXECUTABLE': sys.executable,
        'RUNNER_MAX_MEMORY_MB': '128',
        'RUNNER_MAX_PIDS': '16',
        'RUNNER_MAX_OUTPUT_BYTES': '4096',
    }
    values.update(overrides)
    return RunnerConfig.from_mapping(values)


class StudentEnvironmentTest(unittest.TestCase):
    def test_keeps_platform_basics_and_removes_secrets(self):
        result = _student_environment({
            'SystemRoot': 'C:\\Windows',
            'TEMP': 'C:\\Temp',
            'PATH': '/secret/tools',
            'DJANGO_SECRET_KEY': 'do-not-leak',
            'MINIMAX_API_KEY': 'do-not-leak',
            'RUNNER_SERVICE_SECRET': 'do-not-leak',
        })
        self.assertEqual(result['SystemRoot'], 'C:\\Windows')
        self.assertEqual(result['TEMP'], 'C:\\Temp')
        self.assertNotIn('PATH', result)
        self.assertNotIn('DJANGO_SECRET_KEY', result)
        self.assertNotIn('MINIMAX_API_KEY', result)
        self.assertNotIn('RUNNER_SERVICE_SECRET', result)
        self.assertEqual(result['PYTHONUTF8'], '1')

    def test_platform_process_group_adapters_are_cross_platform(self):
        self.assertEqual(_platform_spawn_kwargs('posix'), {'start_new_session': True})
        self.assertIn('creationflags', _platform_spawn_kwargs('nt'))
        self.assertEqual(
            _windows_taskkill_command(123),
            ['taskkill', '/PID', '123', '/T', '/F'],
        )


class LocalProcessExecutorTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp.name)
        self.executor = LocalProcessExecutor(config(), temp_root=self.temp_root)

    def tearDown(self):
        self.executor.terminate_all()
        self.temp.cleanup()

    def assert_temp_root_empty(self):
        self.assertEqual(list(self.temp_root.iterdir()), [])

    def test_success_with_stdin_stdout_and_stderr(self):
        result = self.executor.execute(
            'import sys\nvalue = input()\nprint(value.upper())\nprint("note", file=sys.stderr)',
            'hello\n',
            wall_seconds=2,
        )
        self.assertEqual(result.status, 'succeeded')
        self.assertEqual(result.stdout, 'HELLO\n')
        self.assertEqual(result.stderr, 'note\n')
        self.assertEqual(result.termination_reason, 'completed')
        self.assert_temp_root_empty()

    def test_nonzero_exit_is_runtime_error(self):
        result = self.executor.execute('raise ValueError("bad")', wall_seconds=2)
        self.assertEqual(result.status, 'runtime_error')
        self.assertIn('ValueError: bad', result.stderr)
        self.assertEqual(result.termination_reason, 'nonzero_exit')
        self.assert_temp_root_empty()

    def test_invalid_utf8_is_replaced_safely(self):
        result = self.executor.execute(
            "import sys; sys.stdout.buffer.write(bytes([255]))", wall_seconds=2,
        )
        self.assertEqual(result.status, 'succeeded')
        self.assertEqual(result.stdout, '\ufffd')

    def test_chinese_output_is_utf8_not_mojibake(self):
        # 回归：`-I` 隐含 `-E` 会忽略 PYTHONIOENCODING，子进程曾退回 GBK 输出乱码。
        result = self.executor.execute('print("你好，白云实验学校")', wall_seconds=2)
        self.assertEqual(result.status, 'succeeded')
        self.assertEqual(result.stdout, '你好，白云实验学校\n')
        self.assertNotIn('\ufffd', result.stdout)

    def test_chinese_stdin_and_stderr_are_utf8(self):
        result = self.executor.execute(
            'import sys\nname = input()\nprint(name)\nprint("提示：" + name, file=sys.stderr)',
            '七年级\n',
            wall_seconds=2,
        )
        self.assertEqual(result.status, 'succeeded')
        self.assertEqual(result.stdout, '七年级\n')
        self.assertEqual(result.stderr, '提示：七年级\n')

    def test_crlf_output_is_normalized_to_lf(self):
        # 回归：Windows 上 Python 把 "\n" 写成 "\r\n"，与测试点文件的 "\n" 不一致，
        # 会把正确的多行程序判成答案错误。
        result = self.executor.execute(
            'print("第一行")\nprint("第二行")', wall_seconds=2,
        )
        self.assertEqual(result.status, 'succeeded')
        self.assertEqual(result.stdout, '第一行\n第二行\n')
        self.assertNotIn('\r', result.stdout)

    def test_wall_timeout_kills_process(self):
        result = self.executor.execute('while True: pass', wall_seconds=0.15)
        self.assertEqual(result.status, 'timed_out')
        self.assertEqual(result.termination_reason, 'wall_time_limit')
        self.assertLess(result.execution_ms, 2000)
        self.assert_temp_root_empty()

    def test_output_limit_is_bounded_and_kills_process(self):
        result = self.executor.execute(
            'import sys\nwhile True:\n sys.stdout.write("x" * 4096)\n sys.stdout.flush()',
            wall_seconds=2,
        )
        self.assertEqual(result.status, 'resource_limited')
        self.assertEqual(result.termination_reason, 'output_limit')
        self.assertTrue(result.output_truncated)
        self.assertLessEqual(len(result.stdout.encode('utf-8')), 4096)
        self.assert_temp_root_empty()

    def test_fast_output_over_limit_cannot_race_success(self):
        result = self.executor.execute(
            'import sys; sys.stdout.write("x" * 4097)', wall_seconds=2,
        )
        self.assertEqual(result.status, 'resource_limited')
        self.assertEqual(result.termination_reason, 'output_limit')
        self.assertEqual(len(result.stdout.encode('utf-8')), 4096)

    def test_exact_output_limit_is_allowed(self):
        result = self.executor.execute(
            'import sys; sys.stdout.write("x" * 4096)', wall_seconds=2,
        )
        self.assertEqual(result.status, 'succeeded')
        self.assertFalse(result.output_truncated)

    def test_memory_limit_is_observed(self):
        constrained = LocalProcessExecutor(
            config(RUNNER_MAX_MEMORY_MB='32'), temp_root=self.temp_root,
        )
        result = constrained.execute(
            'chunks=[]\nwhile True:\n chunks.append(bytearray(1024 * 1024))',
            wall_seconds=3,
        )
        self.assertEqual(result.status, 'resource_limited')
        self.assertEqual(result.termination_reason, 'memory_limit')
        self.assert_temp_root_empty()

    def test_process_limit_kills_descendants(self):
        constrained = LocalProcessExecutor(
            config(RUNNER_MAX_PIDS='2'), temp_root=self.temp_root,
        )
        code = (
            'import subprocess, sys, time\n'
            'children = [subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"]) '
            'for _ in range(3)]\n'
            'print(children[0].pid, flush=True)\n'
            'time.sleep(30)\n'
        )
        result = constrained.execute(code, wall_seconds=3)
        self.assertEqual(result.status, 'resource_limited')
        self.assertEqual(result.termination_reason, 'process_limit')
        child_pid = int(result.stdout.strip())
        for _ in range(20):
            if not psutil.pid_exists(child_pid):
                break
            time.sleep(0.05)
        self.assertFalse(psutil.pid_exists(child_pid))
        self.assert_temp_root_empty()

    @unittest.skipIf(os.name == 'nt', 'Windows 后台进程清理由真实机房专项验收覆盖')
    def test_successful_root_cannot_leave_background_child(self):
        code = (
            'import subprocess, sys\n'
            'child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])\n'
            'print(child.pid, flush=True)\n'
        )
        result = self.executor.execute(code, wall_seconds=2)
        self.assertEqual(result.status, 'succeeded')
        child_pid = int(result.stdout.strip())
        for _ in range(20):
            if not psutil.pid_exists(child_pid):
                break
            time.sleep(0.05)
        self.assertFalse(psutil.pid_exists(child_pid))
        self.assert_temp_root_empty()

    def test_child_environment_does_not_receive_runner_secret(self):
        previous = os.environ.get('RUNNER_SERVICE_SECRET')
        os.environ['RUNNER_SERVICE_SECRET'] = 'top-secret-value'
        try:
            result = self.executor.execute(
                'import os; print(os.environ.get("RUNNER_SERVICE_SECRET", "missing"))',
                wall_seconds=2,
            )
        finally:
            if previous is None:
                os.environ.pop('RUNNER_SERVICE_SECRET', None)
            else:
                os.environ['RUNNER_SERVICE_SECRET'] = previous
        self.assertEqual(result.status, 'succeeded')
        self.assertEqual(result.stdout.strip(), 'missing')


if __name__ == '__main__':
    unittest.main()
