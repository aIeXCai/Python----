import tempfile
import unittest
from pathlib import Path

from scripts.init_local_runner import ensure_config, read_secret, validate_existing


class InitLocalRunnerConfigTest(unittest.TestCase):
    def test_creates_once_without_overwriting_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env.runner.local'
            self.assertTrue(ensure_config(path))
            first = read_secret(path)
            self.assertGreaterEqual(len(first), 32)
            self.assertFalse(ensure_config(path))
            self.assertEqual(read_secret(path), first)

    def test_rejects_invalid_existing_config(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env.runner.local'
            path.write_text('RUNNER_SERVICE_SECRET=short\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, '密钥无效'):
                validate_existing(path)


if __name__ == '__main__':
    unittest.main()
