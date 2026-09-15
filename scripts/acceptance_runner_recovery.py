#!/usr/bin/env python3
"""Exercise Runner crash recovery, Django restart, and queue expiry."""

from __future__ import annotations

import json
import subprocess
import time
import uuid

import psutil
from benchmark_local_runner import PROJECT_ROOT, request_json, runner_pid
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.authtoken.models import Token

from execution.models import ExecutionTask


def stop_runner_abruptly(pid: int) -> None:
    process = psutil.Process(pid)
    command = ' '.join(process.cmdline())
    expected_script = str(PROJECT_ROOT / 'scripts' / 'run_local_runner.py')
    if expected_script not in command:
        raise RuntimeError(f'拒绝停止未经验证的进程 PID={pid}')
    processes = [*process.children(recursive=True), process]
    for item in reversed(processes):
        try:
            item.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(processes, timeout=3)


def main() -> int:
    run_id = uuid.uuid4().hex[:10]
    User = get_user_model()
    user = User.objects.create_user(
        username=f'__step6_recovery_{run_id}', password=None, role='student',
        grade='八年级', class_num='20', student_number=f'R{run_id}',
        display_name='Runner 恢复验收',
    )
    token = Token.objects.create(user=user).key
    recovery_task_id = None
    expiry_task_id = None
    try:
        status, queued = request_json(
            'POST', 'http://127.0.0.1:8080/api/ai/run_code/', token=token,
            body={'code': 'import time\ntime.sleep(3)\nprint("RECOVERED")', 'stdin': ''},
            idempotency_key=str(uuid.uuid4()),
        )
        if status != 202:
            raise RuntimeError(f'恢复测试入队失败: HTTP {status} {queued}')
        recovery_task_id = queued['task_id']

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            status, task = request_json(
                'GET', f'http://127.0.0.1:8080/api/ai/executions/{recovery_task_id}/', token=token,
            )
            if status == 200 and task.get('status') == 'running':
                break
            time.sleep(0.05)
        else:
            raise RuntimeError('任务未在 10 秒内进入 running')

        pid = runner_pid()
        if not pid:
            raise RuntimeError('PID 文件中没有 Runner PID')
        stop_runner_abruptly(pid)

        restarted = subprocess.run(
            ['bash', str(PROJECT_ROOT / 'start_all.sh')], cwd=PROJECT_ROOT,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=40,
        )
        if restarted.returncode != 0:
            raise RuntimeError(f'全栈重启失败:\n{restarted.stdout[-2000:]}')

        deadline = time.monotonic() + 70
        recovered = None
        while time.monotonic() < deadline:
            status, recovered = request_json(
                'GET', f'http://127.0.0.1:8080/api/ai/executions/{recovery_task_id}/', token=token,
            )
            if status == 200 and recovered.get('status') not in {'queued', 'running'}:
                break
            time.sleep(0.5)
        recovery_row = ExecutionTask.objects.get(public_id=recovery_task_id)

        expired = ExecutionTask.objects.create(
            user=user, task_type='run', status='queued', code='print("TOO_LATE")', stdin='',
            snapshot_hash='e' * 64, limits={'wall_seconds': 2},
            idempotency_key=str(uuid.uuid4()), expires_at=timezone.now() - timezone.timedelta(seconds=1),
        )
        expiry_task_id = str(expired.public_id)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            expired.refresh_from_db()
            if expired.status == 'cancelled':
                break
            time.sleep(0.2)

        new_runner_pid = runner_pid()
        residual_children = []
        if new_runner_pid:
            try:
                residual_children = [
                    child.pid for child in psutil.Process(new_runner_pid).children(recursive=True)
                    if child.is_running()
                ]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        report = {
            'passed': (
                recovered is not None
                and recovered.get('status') == 'succeeded'
                and recovered.get('output', '').strip() == 'RECOVERED'
                and recovery_row.attempt_count == 2
                and expired.status == 'cancelled'
                and expired.result_detail.get('reason') == 'queue_expired'
                and not residual_children
            ),
            'runner_crash_task_status': recovered.get('status') if recovered else None,
            'runner_crash_task_output': recovered.get('output', '').strip() if recovered else None,
            'runner_crash_attempt_count': recovery_row.attempt_count,
            'django_restart': 'succeeded',
            'expired_task_status': expired.status,
            'expired_task_reason': expired.result_detail.get('reason'),
            'residual_runner_children': residual_children,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if report['passed'] else 1
    finally:
        User.objects.filter(pk=user.pk).delete()


if __name__ == '__main__':
    raise SystemExit(main())
