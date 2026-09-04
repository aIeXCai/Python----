import hashlib
import json
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from ai_courses.models import Submission
from users.models import CustomUser

from .constants import (
    FINAL_STATUSES,
    GRADE_RESULT_STATUSES,
    RUN_RESULT_STATUSES,
    STATUS_CANCELLED,
    STATUS_QUEUED,
    STATUS_RESOURCE_LIMITED,
    STATUS_RUNNING,
    STATUS_RUNTIME_ERROR,
    STATUS_SUCCEEDED,
    STATUS_SYSTEM_ERROR,
    STATUS_TIMED_OUT,
    STATUS_WRONG_ANSWER,
    TASK_TYPE_GRADE,
    RUNNER_STATUS_ONLINE,
)
from .models import ExecutionTask, RunnerNode, RunnerRequestReceipt


class QueueError(Exception):
    def __init__(self, message, *, status_code=409, code='invalid_task_state'):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


def _token_hash(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _submission_failure(task, message):
    Submission.objects.filter(execution_task=task).update(
        status='error', score=None, error_message=message,
    )


def recover_expired_tasks(*, now=None):
    now = now or timezone.now()
    cancelled = 0
    requeued = 0
    failed = 0
    with transaction.atomic():
        RunnerRequestReceipt.objects.filter(
            created_at__lt=now - timedelta(seconds=settings.RUNNER_RECEIPT_TTL_SECONDS),
        ).delete()
        expired_queued = list(
            ExecutionTask.objects.select_for_update().filter(
                status=STATUS_QUEUED,
                expires_at__lte=now,
            )
        )
        for task in expired_queued:
            task.status = STATUS_CANCELLED
            task.finished_at = now
            task.result_detail = {'reason': 'queue_expired'}
            task.save(update_fields=('status', 'finished_at', 'result_detail', 'updated_at'))
            _submission_failure(task, '排队超时，代码未执行')
            cancelled += 1

        expired_running = list(
            ExecutionTask.objects.select_for_update().filter(
                status=STATUS_RUNNING,
                lease_expires_at__lte=now,
            )
        )
        for task in expired_running:
            task.leased_by = ''
            task.lease_token_hash = ''
            task.lease_expires_at = None
            if task.attempt_count < settings.EXECUTION_MAX_ATTEMPTS:
                task.status = STATUS_QUEUED
                task.expires_at = now + timedelta(seconds=settings.EXECUTION_QUEUE_TTL_SECONDS)
                task.result_detail = {'reason': 'lease_expired_requeued'}
                task.save(update_fields=(
                    'status', 'leased_by', 'lease_token_hash', 'lease_expires_at',
                    'expires_at', 'result_detail', 'updated_at',
                ))
                Submission.objects.filter(execution_task=task).update(status='pending')
                requeued += 1
            else:
                task.status = STATUS_SYSTEM_ERROR
                task.finished_at = now
                task.result_detail = {'reason': 'runner_lost'}
                task.save(update_fields=(
                    'status', 'leased_by', 'lease_token_hash', 'lease_expires_at',
                    'finished_at', 'result_detail', 'updated_at',
                ))
                _submission_failure(task, '执行服务中断，请重新提交')
                failed += 1
    return {'cancelled': cancelled, 'requeued': requeued, 'failed': failed}


def _lock_next_task(now):
    running_users = ExecutionTask.objects.filter(status=STATUS_RUNNING).values('user_id')
    queryset = ExecutionTask.objects.filter(
        status=STATUS_QUEUED,
        expires_at__gt=now,
    ).exclude(user_id__in=running_users).order_by('priority', 'queued_at', 'id')
    if connection.features.has_select_for_update_skip_locked:
        queryset = queryset.select_for_update(skip_locked=True)
    else:
        queryset = queryset.select_for_update()
    return queryset.first()


def claim_task(*, runner_id):
    now = timezone.now()
    recover_expired_tasks(now=now)
    with transaction.atomic():
        try:
            node = RunnerNode.objects.select_for_update().get(runner_id=runner_id)
        except RunnerNode.DoesNotExist as exc:
            raise QueueError(
                'Runner 尚未注册心跳', status_code=403, code='runner_not_registered',
            ) from exc
        if (
            node.status != RUNNER_STATUS_ONLINE
            or node.last_heartbeat_at < now - timedelta(seconds=settings.RUNNER_NODE_STALE_SECONDS)
        ):
            raise QueueError('Runner 当前不可领取任务', code='runner_not_available')
        if ExecutionTask.objects.filter(status=STATUS_RUNNING, leased_by=runner_id).count() >= node.capacity:
            return None
        task = _lock_next_task(now)
        if task is None:
            return None
        CustomUser.objects.select_for_update().get(pk=task.user_id)
        if ExecutionTask.objects.filter(user_id=task.user_id, status=STATUS_RUNNING).exists():
            return None

        token = secrets.token_urlsafe(32)
        task.status = STATUS_RUNNING
        task.started_at = now
        task.leased_by = runner_id
        task.lease_token_hash = _token_hash(token)
        task.lease_expires_at = now + timedelta(seconds=settings.EXECUTION_LEASE_SECONDS)
        task.attempt_count += 1
        task.queue_ms = max(0, int((now - task.queued_at).total_seconds() * 1000))
        task.save(update_fields=(
            'status', 'started_at', 'leased_by', 'lease_token_hash',
            'lease_expires_at', 'attempt_count', 'queue_ms', 'updated_at',
        ))
        Submission.objects.filter(execution_task=task).update(status='running')
        return {
            'task_id': str(task.public_id),
            'task_type': task.task_type,
            'code': task.code,
            'stdin': task.stdin,
            'test_snapshot': task.test_snapshot,
            'snapshot_hash': task.snapshot_hash,
            'limits': task.limits,
            'lease_token': token,
            'lease_expires_at': task.lease_expires_at,
            'protocol_version': settings.RUNNER_PROTOCOL_VERSION,
        }


def _locked_leased_task(*, task_id, runner_id, lease_token):
    try:
        task = ExecutionTask.objects.select_for_update().get(public_id=task_id)
    except ExecutionTask.DoesNotExist as exc:
        raise QueueError('任务不存在', status_code=404, code='task_not_found') from exc
    if task.leased_by != runner_id or not hmac_safe_equal(task.lease_token_hash, _token_hash(lease_token)):
        raise QueueError('任务租约无效', status_code=403, code='invalid_lease')
    return task


def hmac_safe_equal(left, right):
    return secrets.compare_digest(left, right)


def heartbeat_task(*, task_id, runner_id, lease_token):
    now = timezone.now()
    with transaction.atomic():
        task = _locked_leased_task(
            task_id=task_id, runner_id=runner_id, lease_token=lease_token,
        )
        if task.status != STATUS_RUNNING:
            raise QueueError('任务已不在执行中')
        if task.lease_expires_at and task.lease_expires_at <= now:
            raise QueueError('任务租约已过期', code='lease_expired')
        task.lease_expires_at = now + timedelta(seconds=settings.EXECUTION_LEASE_SECONDS)
        task.save(update_fields=('lease_expires_at', 'updated_at'))
        return {'task_id': str(task.public_id), 'lease_expires_at': task.lease_expires_at}


def _validate_result(task, result):
    allowed = GRADE_RESULT_STATUSES if task.task_type == TASK_TYPE_GRADE else RUN_RESULT_STATUSES
    result_status = result.get('status')
    if result_status not in allowed:
        raise QueueError('结果状态无效', status_code=400, code='invalid_result')
    stdout = result.get('stdout', '')
    stderr = result.get('stderr', '')
    if not isinstance(stdout, str) or not isinstance(stderr, str):
        raise QueueError('输出必须是文本', status_code=400, code='invalid_result')
    if len(stdout.encode('utf-8')) + len(stderr.encode('utf-8')) > settings.EXECUTION_MAX_OUTPUT_BYTES:
        raise QueueError('执行输出超出上限', status_code=413, code='result_too_large')
    execution_ms = result.get('execution_ms')
    if not isinstance(execution_ms, int) or isinstance(execution_ms, bool) or execution_ms < 0:
        raise QueueError('执行时长无效', status_code=400, code='invalid_result')
    task_wall_seconds = task.limits.get('task_wall_seconds')
    if isinstance(task_wall_seconds, int) and execution_ms > (task_wall_seconds + 5) * 1000:
        raise QueueError('执行时长超出任务上限', status_code=400, code='invalid_result')
    detail = result.get('detail') or {}
    if not isinstance(detail, dict):
        raise QueueError('结果详情无效', status_code=400, code='invalid_result')
    if len(json.dumps(detail, ensure_ascii=False).encode('utf-8')) > settings.EXECUTION_MAX_RESULT_BYTES:
        raise QueueError('结果详情超出上限', status_code=413, code='result_too_large')
    return result_status, stdout, stderr, execution_ms, detail


def _sanitize_grade_result(task, result_status, detail, raw_score):
    if result_status in (STATUS_SUCCEEDED, STATUS_WRONG_ANSWER):
        if not isinstance(raw_score, (int, float)) or isinstance(raw_score, bool) or not 0 <= raw_score <= 100:
            raise QueueError('评测得分无效', status_code=400, code='invalid_result')
        if result_status == STATUS_SUCCEEDED and raw_score != 100:
            raise QueueError('通过状态必须为 100 分', status_code=400, code='invalid_result')
        if result_status == STATUS_WRONG_ANSWER and raw_score >= 100:
            raise QueueError('错误答案状态不能为 100 分', status_code=400, code='invalid_result')
        score = float(raw_score)
    elif result_status == STATUS_SYSTEM_ERROR:
        if raw_score is not None:
            raise QueueError('系统错误不得生成成绩', status_code=400, code='invalid_result')
        score = None
    else:
        if raw_score is not None and (
            not isinstance(raw_score, (int, float))
            or isinstance(raw_score, bool)
            or not 0 <= raw_score <= 100
        ):
            raise QueueError('评测得分无效', status_code=400, code='invalid_result')
        score = float(raw_score or 0)

    cases = (task.test_snapshot or {}).get('cases', [])
    raw_tests = detail.get('tests', [])
    if not isinstance(raw_tests, list) or len(raw_tests) > len(cases):
        raise QueueError('测试点结果数量无效', status_code=400, code='invalid_result')
    expected_by_number = {case['number']: case.get('output', '') for case in cases}
    safe_tests = []
    seen = set()
    allowed_case_statuses = {'passed', 'wrong_answer', 'runtime_error', 'timed_out', 'resource_limited'}
    for item in raw_tests:
        if not isinstance(item, dict):
            raise QueueError('测试点结果无效', status_code=400, code='invalid_result')
        number = item.get('number')
        case_status = item.get('status')
        if number not in expected_by_number or number in seen or case_status not in allowed_case_statuses:
            raise QueueError('测试点结果无效', status_code=400, code='invalid_result')
        seen.add(number)
        actual = item.get('actual_output', '')
        case_error = item.get('stderr', '')
        case_ms = item.get('execution_ms', 0)
        if not isinstance(actual, str) or not isinstance(case_error, str) or not isinstance(case_ms, int):
            raise QueueError('测试点结果无效', status_code=400, code='invalid_result')
        if len(actual.encode('utf-8')) > settings.EXECUTION_MAX_OUTPUT_BYTES:
            raise QueueError('测试点输出超出上限', status_code=413, code='result_too_large')
        safe_tests.append({
            'number': number,
            'status': case_status,
            'actual_output': actual,
            'expected_output': expected_by_number[number],
            'stderr': case_error,
            'execution_ms': case_ms,
        })
    return score, {'tests': safe_tests, 'termination_reason': detail.get('termination_reason', '')}


def _submission_status(result_status):
    return {
        STATUS_SUCCEEDED: 'accepted',
        STATUS_WRONG_ANSWER: 'wrong_answer',
        STATUS_RUNTIME_ERROR: 'runtime_error',
        STATUS_TIMED_OUT: 'timeout',
        STATUS_RESOURCE_LIMITED: 'error',
        STATUS_SYSTEM_ERROR: 'error',
    }[result_status]


def _submission_report(status_value, detail):
    labels = {
        STATUS_SUCCEEDED: '全部通过', STATUS_WRONG_ANSWER: '答案错误',
        STATUS_RUNTIME_ERROR: '运行时错误', STATUS_TIMED_OUT: '执行超时',
        STATUS_RESOURCE_LIMITED: '资源使用超限', STATUS_SYSTEM_ERROR: '执行服务错误',
    }
    lines = [labels[status_value]]
    for item in detail.get('tests', []):
        lines.append(f"测试点 {item['number']}: {item['status']}")
    return '\n'.join(lines)


def complete_task(*, task_id, runner_id, lease_token, result):
    now = timezone.now()
    with transaction.atomic():
        task = _locked_leased_task(
            task_id=task_id, runner_id=runner_id, lease_token=lease_token,
        )
        if task.status in FINAL_STATUSES:
            return task, False
        if task.status != STATUS_RUNNING:
            raise QueueError('任务已不在执行中')
        if task.lease_expires_at and task.lease_expires_at <= now:
            raise QueueError('任务租约已过期', code='lease_expired')

        result_status, stdout, stderr, execution_ms, detail = _validate_result(task, result)
        score = None
        if task.task_type == TASK_TYPE_GRADE:
            score, detail = _sanitize_grade_result(task, result_status, detail, result.get('score'))
        else:
            detail = {
                'termination_reason': detail.get('termination_reason', ''),
                'output_truncated': bool(detail.get('output_truncated', False)),
            }

        task.status = result_status
        task.stdout = stdout
        task.stderr = stderr
        task.result_detail = detail
        task.score = score
        task.execution_ms = execution_ms
        task.finished_at = now
        task.lease_expires_at = None
        task.save(update_fields=(
            'status', 'stdout', 'stderr', 'result_detail', 'score',
            'execution_ms', 'finished_at', 'lease_expires_at', 'updated_at',
        ))
        if task.task_type == TASK_TYPE_GRADE:
            Submission.objects.filter(execution_task=task).update(
                status=_submission_status(result_status),
                score=score,
                error_message='' if result_status == STATUS_SUCCEEDED else _submission_report(result_status, detail),
            )
        return task, True


def update_runner_node(*, runner_id, data):
    now = timezone.now()
    node, _created = RunnerNode.objects.update_or_create(
        runner_id=runner_id,
        defaults={
            'protocol_version': data['protocol_version'],
            'sandbox_image_digest': data['sandbox_image_digest'],
            'capacity': data['capacity'],
            'active_slots': data['active_slots'],
            'status': data['status'],
            'last_heartbeat_at': now,
            'last_error': data.get('last_error', ''),
        },
    )
    return node
