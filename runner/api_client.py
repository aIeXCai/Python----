from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable

import requests

from .config import RunnerConfig
from .signer import sign_request


class RunnerApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, code: str = ''):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


@dataclass(frozen=True)
class _PreparedRequest:
    path: str
    body: bytes
    request_id: str


class RunnerApiClient:
    """Small signed client for the existing Django runner.v1 protocol."""

    def __init__(
        self,
        config: RunnerConfig,
        *,
        session: requests.Session | None = None,
        clock: Callable[[], float] = time.time,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        self.config = config
        self.session = session or requests.Session()
        self.clock = clock
        self.sleeper = sleeper

    @staticmethod
    def _json_body(payload: dict[str, Any]) -> bytes:
        return json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')

    def _prepare(self, path: str, payload: dict[str, Any]) -> _PreparedRequest:
        return _PreparedRequest(path=path, body=self._json_body(payload), request_id=str(uuid.uuid4()))

    def _headers(self, request: _PreparedRequest, timestamp: int) -> dict[str, str]:
        signature = sign_request(
            secret=self.config.service_secret,
            method='POST',
            path=request.path,
            timestamp=timestamp,
            request_id=request.request_id,
            body=request.body,
        )
        return {
            'Content-Type': 'application/json',
            'X-Runner-Id': self.config.runner_id,
            'X-Runner-Timestamp': str(timestamp),
            'X-Runner-Request-Id': request.request_id,
            'X-Runner-Signature': f'sha256={signature}',
        }

    def _post(
        self, path: str, payload: dict[str, Any], *, retryable: bool,
    ) -> dict[str, Any]:
        prepared = self._prepare(path, payload)
        attempts = self.config.http_retries + 1 if retryable else 1
        last_network_error: Exception | None = None

        for attempt in range(attempts):
            timestamp = int(self.clock())
            try:
                response = self.session.post(
                    f'{self.config.web_internal_url}{path}',
                    data=prepared.body,
                    headers=self._headers(prepared, timestamp),
                    timeout=self.config.http_timeout_seconds,
                )
            except requests.RequestException as exc:
                last_network_error = exc
                if attempt + 1 >= attempts:
                    break
                self.sleeper(min(2.0, 0.2 * (2 ** attempt)))
                continue

            if response.status_code >= 500 and attempt + 1 < attempts:
                self.sleeper(min(2.0, 0.2 * (2 ** attempt)))
                continue

            try:
                data = response.json()
            except (TypeError, ValueError) as exc:
                raise RunnerApiError(
                    'Runner Web 返回了无法解析的响应', status_code=response.status_code,
                    code='invalid_web_response',
                ) from exc
            if not isinstance(data, dict):
                raise RunnerApiError(
                    'Runner Web 返回格式无效', status_code=response.status_code,
                    code='invalid_web_response',
                )
            if not 200 <= response.status_code < 300:
                raise RunnerApiError(
                    str(data.get('error') or 'Runner Web 请求失败'),
                    status_code=response.status_code,
                    code=str(data.get('code') or 'runner_web_error'),
                )
            return data

        raise RunnerApiError(
            '无法连接 Runner Web 内部接口', code='runner_web_unreachable',
        ) from last_network_error

    def node_heartbeat(
        self, *, active_slots: int, status: str = 'online', last_error: str = '',
    ) -> dict[str, Any]:
        return self._post('/internal/runner/v1/nodes/heartbeat', {
            'protocol_version': self.config.protocol_version,
            'sandbox_image_digest': 'local-subprocess-v1',
            'capacity': self.config.concurrency,
            'active_slots': active_slots,
            'status': status,
            'last_error': last_error[:500],
        }, retryable=True)

    def claim_task(self) -> dict[str, Any] | None:
        response = self._post('/internal/runner/v1/tasks/claim', {
            'protocol_version': self.config.protocol_version,
        }, retryable=False)
        task = response.get('task')
        if task is not None and not isinstance(task, dict):
            raise RunnerApiError('Runner Web 返回的任务格式无效', code='invalid_task_envelope')
        return task

    def task_heartbeat(self, task_id: str, lease_token: str) -> dict[str, Any]:
        return self._post(f'/internal/runner/v1/tasks/{task_id}/heartbeat', {
            'protocol_version': self.config.protocol_version,
            'lease_token': lease_token,
        }, retryable=True)

    def complete_task(
        self, task_id: str, lease_token: str, result: dict[str, Any],
    ) -> dict[str, Any]:
        return self._post(f'/internal/runner/v1/tasks/{task_id}/complete', {
            'protocol_version': self.config.protocol_version,
            'lease_token': lease_token,
            **result,
        }, retryable=True)
