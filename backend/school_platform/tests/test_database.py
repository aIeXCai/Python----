from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from school_platform.database import (
    build_database_settings,
    get_database_engine,
    get_non_negative_int,
)


class DatabaseConfigurationTests(SimpleTestCase):
    base_dir = Path('/tmp/platform-database-tests')

    def mysql_environment(self, **overrides):
        values = {
            'DJANGO_DB_ENGINE': 'mysql',
            'DJANGO_DB_NAME': 'python_learning_stage2',
            'DJANGO_DB_USER': 'python_stage2',
            'DJANGO_DB_PASSWORD': 'test-only-password',
            'DJANGO_DB_HOST': '127.0.0.1',
            'DJANGO_DB_PORT': '3308',
            'DJANGO_DB_CONN_MAX_AGE': '30',
            'DJANGO_DB_CONNECT_TIMEOUT': '4',
            'DJANGO_DB_TEST_NAME': 'python_learning_stage2_test',
        }
        values.update(overrides)
        return values

    def test_development_defaults_to_sqlite(self):
        config = build_database_settings(self.base_dir, 'development', {})
        self.assertEqual(config['ENGINE'], 'django.db.backends.sqlite3')
        self.assertEqual(config['NAME'], self.base_dir / 'db.sqlite3')

    def test_sqlite_accepts_snapshot_path(self):
        config = build_database_settings(
            self.base_dir,
            'test',
            {'DJANGO_DB_ENGINE': 'sqlite', 'DJANGO_DB_NAME': '/tmp/source.sqlite3'},
        )
        self.assertEqual(config['NAME'], Path('/tmp/source.sqlite3'))

    def test_mysql_configuration(self):
        config = build_database_settings(
            self.base_dir, 'development', self.mysql_environment()
        )
        self.assertEqual(config['ENGINE'], 'django.db.backends.mysql')
        self.assertEqual(config['PORT'], 3308)
        self.assertEqual(config['OPTIONS']['charset'], 'utf8mb4')
        self.assertEqual(config['OPTIONS']['isolation_level'], 'read committed')
        self.assertEqual(config['TEST']['NAME'], 'python_learning_stage2_test')

    def test_rejects_unknown_engine(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'DJANGO_DB_ENGINE'):
            get_database_engine({'DJANGO_DB_ENGINE': 'postgres'})

    def test_rejects_invalid_integer(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'TIMEOUT'):
            get_non_negative_int('TIMEOUT', 5, {'TIMEOUT': 'slow'})

    def test_rejects_invalid_port(self):
        for port in ('0', '65536', 'not-a-port'):
            with self.subTest(port=port), self.assertRaises(ImproperlyConfigured):
                build_database_settings(
                    self.base_dir,
                    'development',
                    self.mysql_environment(DJANGO_DB_PORT=port),
                )

    def test_rejects_missing_mysql_parameters(self):
        for variable in (
            'DJANGO_DB_NAME',
            'DJANGO_DB_USER',
            'DJANGO_DB_PASSWORD',
            'DJANGO_DB_HOST',
        ):
            with self.subTest(variable=variable), self.assertRaisesMessage(
                ImproperlyConfigured, variable
            ):
                build_database_settings(
                    self.base_dir,
                    'development',
                    self.mysql_environment(**{variable: ''}),
                )

    def test_production_rejects_sqlite(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'DJANGO_DB_ENGINE=mysql'):
            build_database_settings(self.base_dir, 'production', {})

    def test_production_accepts_complete_mysql_configuration(self):
        config = build_database_settings(
            self.base_dir, 'production', self.mysql_environment()
        )
        self.assertEqual(config['ENGINE'], 'django.db.backends.mysql')
