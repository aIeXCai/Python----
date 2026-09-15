#!/usr/bin/env python3
"""Run a disposable 40-student submission burst against the local stack."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import psutil


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = PROJECT_ROOT / 'backend'
sys.path.insert(0, str(BACKEND_ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_platform.settings')
os.environ.setdefault('DJANGO_ENV', 'development')

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.db import close_old_connections  # noqa: E402
from rest_framework.authtoken.models import Token  # noqa: E402

from ai_courses.models import Problem  # noqa: E402
from execution.models import ExecutionTask, RunnerNode  # noqa: E402


TERMINAL = {'succeeded', 'wrong_answer', 'runtime_error', 'timed_out', 'resource_limited', 'system_error', 'cancelled'}
CORRECT_CODE = 'print("Hello")\nprint("How are you?")\nprint("I am fine, thank you, and you?")'


def request_json(method: str, url: str, *, token: str, body: dict | None = None, idempotency_key: str = ''):
    payload = None if body is None else json.dumps(body).encode('utf-8')
    headers = {'Authorization': f'Token {token}', 'Accept': 'application/json'}
    if payload is not None:
        headers['Content-Type'] = 'application/json'
    if idempotency_key:
        headers['Idempotency-Key'] = idempotency_key
    request = Request(url, data=payload, headers=headers, method=method)
    try:
        with urlopen(request, timeout=35) as response:
            raw = response.read().decode('utf-8')
            return response.status, json.loads(raw) if raw else {}
    except HTTPError as exc:
        raw = exc.read().decode('utf-8', errors='replace')
        try:
            detail = json.loads(raw)
        except json.JSONDecodeError:
            detail = {'raw': raw[:500]}
        return exc.code, detail
    except (TimeoutError, URLError) as exc:
        return 0, {'error': str(exc)}


def percentile(values: list[int], fraction: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def runner_pid() -> int | None:
    pid_file = PROJECT_ROOT / '.server_pids'
    if not pid_file.exists():
        return None
    for line in pid_file.read_text(encoding='utf-8').splitlines():
        if line.startswith('runner=') and line[7:].isdigit():
            return int(line[7:])
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--students', type=int, default=40)
    parser.add_argument('--base-url', default='http://127.0.0.1:8080')
    parser.add_argument('--timeout', type=float, default=120)
    parser.add_argument('--student-delay', type=float, default=0.4)
    args = parser.parse_args()
    if not 1 <= args.students <= 200:
        parser.error('--students must be between 1 and 200')
    if not 0 <= args.student_delay <= 4:
        parser.error('--student-delay must be between 0 and 4 seconds')
    submitted_code = CORRECT_CODE
    if args.student_delay:
        submitted_code = f'import time\ntime.sleep({args.student_delay})\n{CORRECT_CODE}'

    run_id = uuid.uuid4().hex[:10]
    users = []
    tokens: list[str] = []
    task_ids: list[str] = []
    responses: list[tuple[int, str, dict]] = []
    max_active_slots = 0
    stop_sampling = threading.Event()
    sample_errors: list[str] = []

    def sample_runner():
        nonlocal max_active_slots
        while not stop_sampling.wait(0.05):
            try:
                close_old_connections()
                active = max(RunnerNode.objects.values_list('active_slots', flat=True), default=0)
                max_active_slots = max(max_active_slots, active)
            except Exception as exc:  # metrics must not abort the load test
                sample_errors.append(type(exc).__name__)
            finally:
                close_old_connections()

    try:
        Problem.objects.get(problem_id='problem1')
        runner_capacity = max(RunnerNode.objects.values_list('capacity', flat=True), default=0)
        User = get_user_model()
        for index in range(args.students):
            user = User(
                username=f'__runner_load_{run_id}_{index + 1}',
                role='student',
                grade='八年级',
                class_num='20',
                student_number=f'L{run_id}{index + 1}',
                display_name=f'负载测试{index + 1}',
            )
            user.set_unusable_password()
            user.save()
            users.append(user)
            tokens.append(Token.objects.create(user=user).key)

        barrier = threading.Barrier(args.students)

        def submit(index: int):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                status, body = request_json(
                    'POST', f'{args.base_url}/api/ai/submissions/', token=tokens[index],
                    body={'problem_id': 'problem1', 'code': submitted_code},
                    idempotency_key=str(uuid.uuid5(uuid.NAMESPACE_URL, f'step6-{run_id}-{index + 1}')),
                )
                return status, tokens[index], body
            finally:
                close_old_connections()

        sampler = threading.Thread(target=sample_runner, daemon=True)
        sampler.start()
        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=args.students) as pool:
            futures = [pool.submit(submit, index) for index in range(args.students)]
            for future in as_completed(futures):
                responses.append(future.result())

        accepted = [(body['task_id'], token) for status, token, body in responses if status == 202 and body.get('task_id')]
        task_ids = [task_id for task_id, _token in accepted]
        deadline = time.monotonic() + args.timeout
        last_status: dict[str, str] = {}
        while task_ids and time.monotonic() < deadline:
            all_terminal = True
            for task_id, token in accepted:
                status, body = request_json(
                    'GET', f'{args.base_url}/api/ai/executions/{task_id}/', token=token,
                )
                task_status = body.get('status') if status == 200 else f'http_{status}'
                last_status[task_id] = task_status
                if task_status not in TERMINAL:
                    all_terminal = False
            if all_terminal:
                break
            time.sleep(0.2)

        elapsed_ms = round((time.monotonic() - started) * 1000)
        stop_sampling.set()
        sampler.join(timeout=2)
        tasks = list(ExecutionTask.objects.filter(public_id__in=task_ids))
        queue_values = [task.queue_ms for task in tasks if task.queue_ms is not None]
        statuses = {}
        for task in tasks:
            statuses[task.status] = statuses.get(task.status, 0) + 1

        time.sleep(0.3)
        residual_children = []
        pid = runner_pid()
        if pid:
            try:
                residual_children = [child.pid for child in psutil.Process(pid).children(recursive=True) if child.is_running()]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                residual_children = []

        report = {
            'students': args.students,
            'accepted_http_202': len(task_ids),
            'rejected_or_failed': args.students - len(task_ids),
            'http_statuses': {str(code): sum(1 for status, _token, _body in responses if status == code) for code in sorted({status for status, _token, _body in responses})},
            'failure_examples': [body for status, _token, body in responses if status != 202][:3],
            'unique_task_ids': len(set(task_ids)),
            'duplicate_task_ids': len(task_ids) - len(set(task_ids)),
            'terminal_tasks': sum(count for status, count in statuses.items() if status in TERMINAL),
            'task_statuses': statuses,
            'score_100': sum(1 for task in tasks if task.score == 100),
            'max_attempt_count': max((task.attempt_count for task in tasks), default=0),
            'max_runner_active_slots': max_active_slots,
            'runner_capacity': runner_capacity,
            'queue_ms_p50': percentile(queue_values, 0.50),
            'queue_ms_p95': percentile(queue_values, 0.95),
            'total_elapsed_ms': elapsed_ms,
            'residual_runner_children': residual_children,
            'sampler_errors': sorted(set(sample_errors)),
        }
        report['passed'] = all((
            report['accepted_http_202'] == args.students,
            report['unique_task_ids'] == args.students,
            report['terminal_tasks'] == args.students,
            report['task_statuses'] == {'succeeded': args.students},
            report['score_100'] == args.students,
            report['max_attempt_count'] == 1,
            report['runner_capacity'] > 0,
            0 < report['max_runner_active_slots'] <= report['runner_capacity'],
            not report['residual_runner_children'],
        ))
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if report['passed'] else 1
    finally:
        stop_sampling.set()
        if users:
            get_user_model().objects.filter(pk__in=[user.pk for user in users]).delete()


if __name__ == '__main__':
    raise SystemExit(main())
