#!/usr/bin/env python3
from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / '.env.runner.local'


def render_config(secret: str) -> str:
    return f'''# Local Runner configuration. Never commit this file.
CODE_EXECUTION_ENABLED=true
EXECUTION_REQUIRE_HEALTHY_RUNNER=true
EXECUTION_QUEUE_TTL_SECONDS=300

RUNNER_ID=local-runner-01
RUNNER_WEB_INTERNAL_URL=http://127.0.0.1:8080
RUNNER_SERVICE_SECRET={secret}
RUNNER_PROTOCOL_VERSION=runner.v1
RUNNER_CONCURRENCY=2
RUNNER_HEARTBEAT_SECONDS=5
RUNNER_CLAIM_IDLE_SECONDS=0.5
RUNNER_HTTP_TIMEOUT_SECONDS=5
RUNNER_HTTP_RETRIES=3
RUNNER_MAX_MEMORY_MB=128
RUNNER_MAX_PIDS=16
RUNNER_MAX_OUTPUT_BYTES=131072
RUNNER_MAX_CASE_SECONDS=5
RUNNER_MAX_TASK_SECONDS=30
RUNNER_SHUTDOWN_GRACE_SECONDS=10
'''


def read_secret(path: Path) -> str:
    if not path.is_file():
        return ''
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if line.startswith('RUNNER_SERVICE_SECRET='):
            return line.split('=', 1)[1]
    return ''


def validate_existing(path: Path) -> None:
    secret = read_secret(path)
    if len(secret) < 32 or secret.startswith('replace-'):
        raise ValueError('本机 Runner 配置存在，但服务密钥无效')


def ensure_config(path: Path = DEFAULT_CONFIG_PATH) -> bool:
    """Create a secure local config once. Return True only when created."""
    if path.exists():
        validate_existing(path)
        return False
    path.write_text(render_config(secrets.token_urlsafe(48)), encoding='utf-8')
    try:
        path.chmod(0o600)
    except OSError:
        # Windows ACLs are not represented by POSIX modes.
        pass
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='初始化跨平台本机 Runner 配置')
    parser.add_argument('--check', action='store_true', help='只检查配置，不创建')
    parser.add_argument('--path', type=Path, default=DEFAULT_CONFIG_PATH, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.check:
            validate_existing(args.path)
            print(f'本机 Runner 配置有效：{args.path}')
        else:
            created = ensure_config(args.path)
            action = '已创建' if created else '已存在且有效'
            print(f'本机 Runner 配置{action}：{args.path}')
    except (OSError, ValueError) as exc:
        print(f'本机 Runner 配置错误：{exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
