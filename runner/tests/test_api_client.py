import hashlib
import hmac
import json
import sys
import unittest

import requests

from runner.api_client import RunnerApiClient, RunnerApiError
from runner.config import RunnerConfig


SECRET = 'runner-test-secret-that-is-long-enough-123456'


class FakeResponse:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self._data = {} if data is None else data

    def json(self):
        return self._data


class FakeSession:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def config(**overrides):
    values = {
        'RUNNER_SERVICE_SECRET': SECRET,
        'RUNNER_PYTHON_EXECUTABLE': sys.executable,
        'RUNNER_HTTP_RETRIES': '2',
    }
    values.update(overrides)
    return RunnerConfig.from_mapping(values)


class RunnerApiClientTest(unittest.TestCase):
    def test_unicode_body_and_signature_match_server_contract(self):
        session = FakeSession([FakeResponse(data={'task': None})])
        client = RunnerApiClient(config(), session=session, clock=lambda: 123456, sleeper=lambda _: None)
        self.assertIsNone(client.claim_task())

        url, request = session.calls[0]
        self.assertEqual(url, 'http://127.0.0.1:8080/internal/runner/v1/tasks/claim')
        body = request['data']
        self.assertEqual(body, b'{"protocol_version":"runner.v1"}')
        headers = request['headers']
        body_hash = hashlib.sha256(body).hexdigest()
        canonical = '\n'.join((
            'POST', '/internal/runner/v1/tasks/claim', '123456',
            headers['X-Runner-Request-Id'], body_hash,
        ))
        expected = hmac.new(SECRET.encode(), canonical.encode(), hashlib.sha256).hexdigest()
        self.assertEqual(headers['X-Runner-Signature'], f'sha256={expected}')

    def test_retryable_request_reuses_request_id_and_body(self):
        session = FakeSession([
            requests.ConnectionError('offline'),
            FakeResponse(503, {'error': 'busy'}),
            FakeResponse(200, {'runner_id': 'local-runner-01'}),
        ])
        client = RunnerApiClient(config(), session=session, clock=lambda: 123456, sleeper=lambda _: None)
        result = client.node_heartbeat(active_slots=1)
        self.assertEqual(result['runner_id'], 'local-runner-01')
        self.assertEqual(len(session.calls), 3)
        ids = {call[1]['headers']['X-Runner-Request-Id'] for call in session.calls}
        bodies = {call[1]['data'] for call in session.calls}
        self.assertEqual(len(ids), 1)
        self.assertEqual(len(bodies), 1)

    def test_claim_is_never_retried_after_ambiguous_failure(self):
        session = FakeSession([
            requests.ConnectionError('response lost'),
            FakeResponse(200, {'task': None}),
        ])
        client = RunnerApiClient(config(), session=session, clock=lambda: 123456, sleeper=lambda _: None)
        with self.assertRaisesRegex(RunnerApiError, '无法连接'):
            client.claim_task()
        self.assertEqual(len(session.calls), 1)

    def test_error_response_keeps_safe_status_and_code(self):
        session = FakeSession([FakeResponse(409, {'error': '协议不匹配', 'code': 'protocol_mismatch'})])
        client = RunnerApiClient(config(), session=session, clock=lambda: 123456)
        with self.assertRaises(RunnerApiError) as caught:
            client.claim_task()
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(caught.exception.code, 'protocol_mismatch')

    def test_complete_payload_contains_lease_and_result(self):
        session = FakeSession([FakeResponse(200, {'applied': True})])
        client = RunnerApiClient(config(), session=session, clock=lambda: 123456)
        client.complete_task('task-id', 'lease-token-value-that-is-long-enough-123', {
            'status': 'succeeded', 'stdout': '你好', 'stderr': '',
            'execution_ms': 1, 'detail': {'termination_reason': 'completed'},
        })
        payload = json.loads(session.calls[0][1]['data'])
        self.assertEqual(payload['protocol_version'], 'runner.v1')
        self.assertEqual(payload['lease_token'], 'lease-token-value-that-is-long-enough-123')
        self.assertEqual(payload['stdout'], '你好')


if __name__ == '__main__':
    unittest.main()
