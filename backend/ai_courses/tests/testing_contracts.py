"""Reusable assertions for the AI mixed-quiz API contract tests."""

import re
from decimal import Decimal, InvalidOperation

from django.utils import timezone
from django.utils.dateparse import parse_datetime


DECIMAL_ONE_PLACE_PATTERN = re.compile(r'^(0|[1-9]\d{0,2})\.\d$')


class APIContractAssertions:
    """Assertions shared by future quiz API tests without production coupling."""

    def assert_api_error(self, response, *, status_code, code):
        self.assertEqual(response.status_code, status_code)
        self.assertIsInstance(response.data, dict)
        self.assertEqual(response.data.get('code'), code)
        self.assertIsInstance(response.data.get('error'), str)
        self.assertTrue(response.data['error'].strip())

    def assert_decimal_string(self, value, *, minimum=Decimal('0.0'), maximum=Decimal('100.0')):
        self.assertIsInstance(value, str)
        self.assertRegex(value, DECIMAL_ONE_PLACE_PATTERN)
        try:
            decimal_value = Decimal(value)
        except InvalidOperation as exc:
            self.fail(f'{value!r} is not a valid decimal string: {exc}')
        self.assertGreaterEqual(decimal_value, minimum)
        self.assertLessEqual(decimal_value, maximum)
        return decimal_value

    def assert_iso8601_datetime(self, value):
        self.assertIsInstance(value, str)
        parsed = parse_datetime(value)
        self.assertIsNotNone(parsed, f'{value!r} is not an ISO 8601 datetime')
        self.assertTrue(timezone.is_aware(parsed), f'{value!r} must include a timezone')
        return parsed
