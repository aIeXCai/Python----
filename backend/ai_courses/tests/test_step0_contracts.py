"""Step 0 contract helpers that future mixed-quiz API tests build on."""

from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from .testing_contracts import APIContractAssertions


class APIContractAssertionsTest(APIContractAssertions, SimpleTestCase):
    def test_api_error_requires_stable_code_and_non_empty_message(self):
        response = SimpleNamespace(
            status_code=409,
            data={'error': '作答版本已变化，请重新加载', 'code': 'attempt_revision_conflict'},
        )
        self.assert_api_error(
            response, status_code=409, code='attempt_revision_conflict',
        )

    def test_decimal_contract_uses_one_place_string_in_score_range(self):
        self.assertEqual(self.assert_decimal_string('0.0'), Decimal('0.0'))
        self.assertEqual(self.assert_decimal_string('37.5'), Decimal('37.5'))
        self.assertEqual(self.assert_decimal_string('100.0'), Decimal('100.0'))

    def test_decimal_contract_rejects_numbers_or_unstable_precision(self):
        with self.assertRaises(AssertionError):
            self.assert_decimal_string(30.0)
        with self.assertRaises(AssertionError):
            self.assert_decimal_string('30')
        with self.assertRaises(AssertionError):
            self.assert_decimal_string('30.00')

    def test_datetime_contract_requires_timezone_aware_iso8601(self):
        parsed = self.assert_iso8601_datetime('2026-09-11T08:30:00Z')
        self.assertEqual(parsed.utcoffset().total_seconds(), 0)
        with self.assertRaises(AssertionError):
            self.assert_iso8601_datetime('2026-09-11T08:30:00')
