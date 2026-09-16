from __future__ import annotations

import hashlib
import hmac


def body_digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def canonical_request(
    method: str, path: str, timestamp: int, request_id: str, body_hash: str,
) -> str:
    return '\n'.join((method.upper(), path, str(timestamp), str(request_id), body_hash))


def sign_request(
    *, secret: str, method: str, path: str, timestamp: int, request_id: str, body: bytes = b'',
) -> str:
    message = canonical_request(method, path, timestamp, request_id, body_digest(body))
    return hmac.new(secret.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
