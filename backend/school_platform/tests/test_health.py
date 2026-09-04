from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse


class HealthCheckTests(TestCase):
    def test_live_returns_ok_without_querying_database(self):
        with patch('school_platform.health.connection.cursor') as cursor:
            response = self.client.get(reverse('health-live'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})
        cursor.assert_not_called()

    def test_live_rejects_non_get_method(self):
        response = self.client.post(reverse('health-live'))
        self.assertEqual(response.status_code, 405)

    def test_ready_returns_ok_when_database_is_available(self):
        response = self.client.get(reverse('health-ready'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_ready_returns_generic_503_when_database_fails(self):
        private_detail = 'database-password=must-not-leak'
        with patch(
            'school_platform.health.connection.cursor',
            side_effect=RuntimeError(private_detail),
        ):
            response = self.client.get(reverse('health-ready'))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'unavailable'})
        self.assertNotIn(private_detail, response.content.decode())
