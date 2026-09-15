import subprocess
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class StartupScriptTest(unittest.TestCase):
    def test_shell_scripts_parse_and_manage_all_three_services(self):
        for name in ('start_all.sh', 'stop_all.sh'):
            result = subprocess.run(
                ('bash', '-n', str(PROJECT_ROOT / name)),
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        start = (PROJECT_ROOT / 'start_all.sh').read_text(encoding='utf-8')
        stop = (PROJECT_ROOT / 'stop_all.sh').read_text(encoding='utf-8')
        for service in ('django=', 'runner=', 'vite='):
            self.assertIn(service, start)
        self.assertIn('frontend/node_modules/vite/bin/vite.js', start)
        self.assertIn('for wanted in runner django vite', stop)
        self.assertNotIn('kill -9 $pid', stop)

    def test_windows_scripts_are_utf8_and_use_project_scoped_process_trees(self):
        start = (PROJECT_ROOT / 'start_all.bat').read_text(encoding='utf-8')
        stop = (PROJECT_ROOT / 'stop_all.bat').read_text(encoding='utf-8')
        self.assertIn('chcp 65001', start)
        self.assertIn('.venv\\Scripts\\python.exe', start)
        self.assertIn('E:\\Anaconda\\envs\\pylearn\\python.exe', start)
        self.assertIn("scripts\\run_local_runner.py", start)
        self.assertIn('runner=%RUNNER_PID%', start)
        self.assertIn('([char]34)', start)
        self.assertIn('taskkill /pid %SERVICE_PID% /t', stop)
        self.assertIn('CommandLine.Contains', stop)
        self.assertNotIn("CommandLine -match 'manage", stop)
        for corrupted_marker in ('�', 'ѧϰ', 'Էú'):
            self.assertNotIn(corrupted_marker, start + stop)


if __name__ == '__main__':
    unittest.main()
