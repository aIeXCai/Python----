from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from school_platform.environment import (
    get_bool,
    get_environment,
    get_int,
    get_list,
    validate_production_settings,
)


class EnvironmentParsingTests(SimpleTestCase):
    def test_environment_accepts_supported_values(self):
        for value in ('development', 'test', 'production'):
            with self.subTest(value=value):
                self.assertEqual(get_environment({'DJANGO_ENV': value}), value)

    def test_environment_rejects_unknown_value(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'DJANGO_ENV'):
            get_environment({'DJANGO_ENV': 'staging'})

    def test_bool_accepts_explicit_true_and_false_values(self):
        for value in ('1', 'true', 'YES', 'on'):
            with self.subTest(value=value):
                self.assertTrue(get_bool('FLAG', environ={'FLAG': value}))
        for value in ('0', 'false', 'NO', 'off'):
            with self.subTest(value=value):
                self.assertFalse(get_bool('FLAG', environ={'FLAG': value}))

    def test_bool_rejects_ambiguous_value(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'FLAG'):
            get_bool('FLAG', environ={'FLAG': 'sometimes'})

    def test_list_trims_whitespace_and_empty_items(self):
        result = get_list('HOSTS', environ={'HOSTS': ' a.example, ,b.example ,, '})
        self.assertEqual(result, ['a.example', 'b.example'])

    def test_int_accepts_default_and_bounded_value(self):
        self.assertEqual(get_int('LIMIT', 12, environ={}), 12)
        self.assertEqual(
            get_int('LIMIT', 12, minimum=1, maximum=30, environ={'LIMIT': ' 18 '}),
            18,
        )

    def test_int_rejects_invalid_or_out_of_range_value(self):
        for environ in ({'LIMIT': 'x'}, {'LIMIT': '0'}, {'LIMIT': '31'}):
            with self.subTest(environ=environ), self.assertRaises(ImproperlyConfigured):
                get_int('LIMIT', 12, minimum=1, maximum=30, environ=environ)


class ProductionValidationTests(SimpleTestCase):
    defaults = {
        'environment': 'production',
        'secret_key': 'x' * 48,
        'debug': False,
        'allowed_hosts': ['example.test'],
        'cors_allowed_origins': [],
        'csrf_trusted_origins': ['https://example.test'],
        'development_secret_key': 'development-only',
        'database_engine': 'mysql',
    }

    def validate(self, **overrides):
        values = {**self.defaults, **overrides}
        return validate_production_settings(**values)

    def test_accepts_safe_production_settings(self):
        self.assertIsNone(self.validate())

    def test_rejects_missing_or_development_secret(self):
        for secret in ('', 'development-only', 'too-short'):
            with self.subTest(secret=secret), self.assertRaisesMessage(
                ImproperlyConfigured, 'DJANGO_SECRET_KEY'
            ):
                self.validate(secret_key=secret)

    def test_rejects_debug_and_wildcard_host(self):
        with self.assertRaises(ImproperlyConfigured) as context:
            self.validate(debug=True, allowed_hosts=['*'])
        message = str(context.exception)
        self.assertIn('DJANGO_DEBUG', message)
        self.assertIn('DJANGO_ALLOWED_HOSTS', message)

    def test_rejects_non_https_cors_and_csrf_origins(self):
        with self.assertRaises(ImproperlyConfigured) as context:
            self.validate(
                cors_allowed_origins=['http://frontend.example.test'],
                csrf_trusted_origins=['example.test'],
            )
        message = str(context.exception)
        self.assertIn('DJANGO_CORS_ALLOWED_ORIGINS', message)
        self.assertIn('DJANGO_CSRF_TRUSTED_ORIGINS', message)

    def test_non_production_environment_skips_production_validation(self):
        self.assertIsNone(
            self.validate(
                environment='development',
                secret_key='',
                debug=True,
                allowed_hosts=['*'],
            )
        )
