import hashlib
import hmac
import time
import uuid
from dataclasses import dataclass

from django.conf import settings


class RunnerAuthError(Exception):
    def __init__(self, message, *, status_code=401, code='runner_auth_failed'):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


@dataclass(frozen=True)
class RunnerRequestIdentity:
    runner_id: str
    request_id: uuid.UUID
    request_hash: str
    endpoint: str


def body_digest(body):
    return hashlib.sha256(body).hexdigest()


def canonical_request(method, path, timestamp, request_id, body_hash):
    return '\n'.join((method.upper(), path, str(timestamp), str(request_id), body_hash))


def sign_runner_request(*, secret, method, path, timestamp, request_id, body=b''):
    message = canonical_request(method, path, timestamp, request_id, body_digest(body))
    return hmac.new(secret.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()


def authenticate_runner_request(request):
    secret = settings.RUNNER_SERVICE_SECRET
    if len(secret) < 32:
        raise RunnerAuthError(
            'Runner 服务尚未正确配置',
            status_code=503,
            code='runner_service_unavailable',
        )

    runner_id = request.headers.get('X-Runner-Id', '').strip()
    timestamp_text = request.headers.get('X-Runner-Timestamp', '').strip()
    request_id_text = request.headers.get('X-Runner-Request-Id', '').strip()
    supplied_signature = request.headers.get('X-Runner-Signature', '').strip()
    if supplied_signature.startswith('sha256='):
        supplied_signature = supplied_signature[7:]
    if not runner_id or len(runner_id) > 100:
        raise RunnerAuthError('Runner ID 无效')
    try:
        timestamp = int(timestamp_text)
        request_id = uuid.UUID(request_id_text)
    except (TypeError, ValueError, AttributeError) as exc:
        raise RunnerAuthError('Runner 时间戳或请求 ID 无效') from exc
    if abs(int(time.time()) - timestamp) > settings.RUNNER_CLOCK_SKEW_SECONDS:
        raise RunnerAuthError('Runner 请求已过期')

    endpoint = request.get_full_path()
    digest = body_digest(request.body)
    expected = sign_runner_request(
        secret=secret,
        method=request.method,
        path=endpoint,
        timestamp=timestamp,
        request_id=request_id,
        body=request.body,
    )
    if not supplied_signature or not hmac.compare_digest(expected, supplied_signature):
        raise RunnerAuthError('Runner 签名无效')
    return RunnerRequestIdentity(runner_id, request_id, digest, f'{request.method.upper()} {endpoint}')
