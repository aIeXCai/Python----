from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = PROJECT_ROOT / '.env.runner.local'


class RunnerConfigError(ValueError):
    """Raised when the runner cannot start safely with its current settings."""


def _integer(values: Mapping[str, str], name: str, default: int, minimum: int, maximum: int) -> int:
    raw = str(values.get(name, default)).strip()
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise RunnerConfigError(f'{name} 必须是整数') from exc
    if not minimum <= value <= maximum:
        raise RunnerConfigError(f'{name} 必须在 {minimum} 到 {maximum} 之间')
    return value


def _number(
    values: Mapping[str, str], name: str, default: float, minimum: float, maximum: float,
) -> float:
    raw = str(values.get(name, default)).strip()
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise RunnerConfigError(f'{name} 必须是数字') from exc
    if not minimum <= value <= maximum:
        raise RunnerConfigError(f'{name} 必须在 {minimum} 到 {maximum} 之间')
    return value


def _boolean(values: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw = values.get(name)
    if raw is None:
        return default
    normalized = str(raw).strip().lower()
    if normalized in {'1', 'true', 'yes', 'on'}:
        return True
    if normalized in {'0', 'false', 'no', 'off'}:
        return False
    raise RunnerConfigError(f'{name} 必须是 true 或 false')


@dataclass(frozen=True)
class RunnerConfig:
    runner_id: str
    web_internal_url: str
    service_secret: str
    protocol_version: str
    concurrency: int
    heartbeat_seconds: int
    claim_idle_seconds: float
    http_timeout_seconds: float
    http_retries: int
    python_executable: str
    max_memory_mb: int
    max_pids: int
    max_output_bytes: int
    max_case_seconds: int
    max_task_seconds: int
    shutdown_grace_seconds: int

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> 'RunnerConfig':
        runner_id = str(values.get('RUNNER_ID', 'local-runner-01')).strip()
        if not runner_id or len(runner_id) > 100:
            raise RunnerConfigError('RUNNER_ID 长度必须在 1 到 100 之间')

        web_url = str(values.get('RUNNER_WEB_INTERNAL_URL', 'http://127.0.0.1:8080')).strip()
        parsed = urlparse(web_url)
        try:
            parsed.port
        except ValueError as exc:
            raise RunnerConfigError('RUNNER_WEB_INTERNAL_URL 端口无效') from exc
        if (
            parsed.scheme not in {'http', 'https'}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path not in {'', '/'}
            or parsed.params
            or parsed.query
            or parsed.fragment
        ):
            raise RunnerConfigError('RUNNER_WEB_INTERNAL_URL 必须是有效的 HTTP(S) 地址')
        allow_remote = _boolean(values, 'RUNNER_ALLOW_REMOTE_WEB', False)
        if parsed.hostname not in {'127.0.0.1', 'localhost', '::1'} and not allow_remote:
            raise RunnerConfigError('远程 Web 地址必须显式设置 RUNNER_ALLOW_REMOTE_WEB=true')
        web_url = web_url.rstrip('/')

        secret = str(values.get('RUNNER_SERVICE_SECRET', ''))
        if len(secret) < 32 or secret.startswith('replace-'):
            raise RunnerConfigError('RUNNER_SERVICE_SECRET 必须是至少 32 位的独立密钥')

        protocol = str(values.get('RUNNER_PROTOCOL_VERSION', 'runner.v1')).strip()
        if not protocol or len(protocol) > 32:
            raise RunnerConfigError('RUNNER_PROTOCOL_VERSION 长度必须在 1 到 32 之间')

        python_executable = str(values.get('RUNNER_PYTHON_EXECUTABLE') or sys.executable).strip()
        if not python_executable or not Path(python_executable).is_file():
            raise RunnerConfigError('RUNNER_PYTHON_EXECUTABLE 不存在或不是文件')

        return cls(
            runner_id=runner_id,
            web_internal_url=web_url,
            service_secret=secret,
            protocol_version=protocol,
            concurrency=_integer(values, 'RUNNER_CONCURRENCY', 2, 1, 32),
            heartbeat_seconds=_integer(values, 'RUNNER_HEARTBEAT_SECONDS', 5, 1, 20),
            claim_idle_seconds=_number(values, 'RUNNER_CLAIM_IDLE_SECONDS', 0.5, 0.05, 30.0),
            http_timeout_seconds=_number(values, 'RUNNER_HTTP_TIMEOUT_SECONDS', 5, 0.5, 60.0),
            http_retries=_integer(values, 'RUNNER_HTTP_RETRIES', 3, 0, 10),
            python_executable=str(Path(python_executable).resolve()),
            max_memory_mb=_integer(values, 'RUNNER_MAX_MEMORY_MB', 128, 32, 4096),
            max_pids=_integer(values, 'RUNNER_MAX_PIDS', 16, 1, 256),
            max_output_bytes=_integer(values, 'RUNNER_MAX_OUTPUT_BYTES', 131072, 1024, 1048576),
            max_case_seconds=_integer(values, 'RUNNER_MAX_CASE_SECONDS', 5, 1, 30),
            max_task_seconds=_integer(values, 'RUNNER_MAX_TASK_SECONDS', 30, 1, 120),
            shutdown_grace_seconds=_integer(values, 'RUNNER_SHUTDOWN_GRACE_SECONDS', 10, 1, 120),
        )


def load_config(env_file: Path | None = None) -> RunnerConfig:
    """Load local settings without overriding explicit process environment."""
    load_dotenv(env_file or DEFAULT_ENV_FILE, override=False)
    return RunnerConfig.from_mapping(os.environ)
