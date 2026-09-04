from cryptography.fernet import Fernet
from django.core.management import call_command
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase, override_settings

from users.models import CustomUser
from users.services import set_student_password

from users.security import (
    PasswordEncryptionError,
    StudentPasswordCipher,
    parse_password_key_config,
)


class PasswordKeyConfigTests(SimpleTestCase):
    def setUp(self):
        self.key = Fernet.generate_key().decode('ascii')

    def test_empty_configuration_is_explicitly_unconfigured(self):
        config = parse_password_key_config('', '')
        self.assertFalse(config.configured)

    def test_valid_configuration_is_read_only(self):
        config = parse_password_key_config(f'v1:{self.key}', 'v1')
        self.assertTrue(config.configured)
        with self.assertRaises(TypeError):
            config.keys['v2'] = self.key

    def test_rejects_missing_pair_duplicate_invalid_key_and_unknown_primary(self):
        cases = [
            (f'v1:{self.key}', ''),
            ('', 'v1'),
            (f'v1:{self.key},v1:{self.key}', 'v1'),
            ('bad id:not-a-key', 'bad id'),
            (f'v1:{self.key}', 'v2'),
        ]
        for raw_keys, primary in cases:
            with self.subTest(primary=primary), self.assertRaises(ImproperlyConfigured):
                parse_password_key_config(raw_keys, primary)


class StudentPasswordCipherTests(SimpleTestCase):
    def setUp(self):
        key = Fernet.generate_key().decode('ascii')
        self.cipher = StudentPasswordCipher(
            parse_password_key_config(f'test-v1:{key}', 'test-v1')
        )

    def test_round_trip_and_randomized_ciphertext(self):
        first, key_id = self.cipher.encrypt('test-password-value')
        second, _ = self.cipher.encrypt('test-password-value')
        self.assertNotEqual(first, second)
        self.assertEqual(key_id, 'test-v1')
        self.assertEqual(self.cipher.decrypt(first, key_id), 'test-password-value')

    def test_tampered_or_unknown_ciphertext_uses_safe_error(self):
        ciphertext, key_id = self.cipher.encrypt('test-password-value')
        for value, supplied_key_id in (
            (ciphertext[:-2] + 'xx', key_id),
            (ciphertext, 'unknown'),
            ('', key_id),
        ):
            with self.subTest(key_id=supplied_key_id), self.assertRaisesMessage(
                PasswordEncryptionError, '暂时无法解密'
            ):
                self.cipher.decrypt(value, supplied_key_id)

    def test_unconfigured_cipher_fails_closed(self):
        with self.assertRaisesMessage(PasswordEncryptionError, '未配置'):
            StudentPasswordCipher(parse_password_key_config('', ''))


class PasswordKeyRotationTests(TestCase):
    def test_rotation_reencrypts_with_primary_key_without_changing_login_hash(self):
        old_key = Fernet.generate_key().decode('ascii')
        new_key = Fernet.generate_key().decode('ascii')
        old_config = parse_password_key_config(f'old:{old_key}', 'old')
        combined_config = parse_password_key_config(
            f'old:{old_key},new:{new_key}', 'new'
        )
        student = CustomUser.objects.create(
            username='rotation-student', role='student',
            grade='七年级', class_num='1', student_number='01',
        )
        with override_settings(STUDENT_PASSWORD_KEY_CONFIG=old_config):
            set_student_password(
                student, 'rotation-test-password',
                validate=False, invalidate_tokens=False,
            )
        old_ciphertext = student.encrypted_password

        with override_settings(STUDENT_PASSWORD_KEY_CONFIG=combined_config):
            call_command('rotate_student_password_keys', '--apply', verbosity=0)
            student.refresh_from_db()
            plaintext = StudentPasswordCipher(combined_config).decrypt(
                student.encrypted_password, student.password_encryption_key_id
            )

        self.assertEqual(student.password_encryption_key_id, 'new')
        self.assertNotEqual(student.encrypted_password, old_ciphertext)
        self.assertEqual(plaintext, 'rotation-test-password')
        self.assertTrue(student.check_password(plaintext))
