from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from users.security import StudentPasswordCipher


class PasswordEncryptionMigrationTests(TransactionTestCase):
    migrate_from = ('users', '0005_add_display_name_plain_password')
    migrate_to = ('users', '0007_remove_plain_password')

    @property
    def executor(self):
        return MigrationExecutor(connection)

    def setUp(self):
        super().setUp()
        executor = self.executor
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps
        User = old_apps.get_model('users', 'CustomUser')
        User.objects.create(
            username='migration-valid', role='student',
            grade='七年级', class_num='1', student_number='01',
            password=make_password('legacy-test-password'),
            plain_password='legacy-test-password',
        )
        User.objects.create(
            username='migration-mismatch', role='student',
            grade='七年级', class_num='1', student_number='02',
            password=make_password('actual-password'), plain_password='stale-value',
        )
        User.objects.create(
            username='migration-missing', role='student',
            grade='七年级', class_num='1', student_number='03',
            password=make_password('actual-password'), plain_password='',
        )
        User.objects.create(
            username='migration-teacher', role='teacher',
            password=make_password('teacher-password'), plain_password=None,
        )
        executor = self.executor
        executor.migrate([self.migrate_to])
        self.apps = executor.loader.project_state([self.migrate_to]).apps

    def tearDown(self):
        self.executor.migrate(self.executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_matching_password_is_encrypted_and_plain_column_removed(self):
        User = self.apps.get_model('users', 'CustomUser')
        user = User.objects.get(username='migration-valid')
        self.assertEqual(user.password_recovery_status, 'available')
        self.assertNotIn('legacy-test-password', user.encrypted_password)
        cipher = StudentPasswordCipher(settings.STUDENT_PASSWORD_KEY_CONFIG)
        self.assertEqual(
            cipher.decrypt(user.encrypted_password, user.password_encryption_key_id),
            'legacy-test-password',
        )
        with connection.cursor() as cursor:
            columns = {
                item.name
                for item in connection.introspection.get_table_description(
                    cursor, User._meta.db_table
                )
            }
        self.assertNotIn('plain_password', columns)

    def test_mismatch_missing_and_teacher_are_not_recoverable(self):
        User = self.apps.get_model('users', 'CustomUser')
        expected = {
            'migration-mismatch': 'hash_mismatch',
            'migration-missing': 'missing_legacy',
            'migration-teacher': 'not_applicable',
        }
        for username, status in expected.items():
            with self.subTest(username=username):
                user = User.objects.get(username=username)
                self.assertEqual(user.password_recovery_status, status)
                self.assertFalse(user.encrypted_password)
                self.assertFalse(user.password_encryption_key_id)
