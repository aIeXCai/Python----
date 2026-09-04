import uuid

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from ai_courses.models import Submission
from users.models import CustomUser

from .constants import STATUS_QUEUED, STATUS_RUNNING, TASK_TYPE_GRADE, TASK_TYPE_RUN
from .models import ExecutionTask
from .snapshots import build_test_snapshot, snapshot_digest


class ExecutionRequestError(Exception):
    def __init__(self, message, *, status_code=400, code='invalid_request'):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


def _validate_text_size(value, setting_name, label):
    if len(value.encode('utf-8')) > getattr(settings, setting_name):
        raise ExecutionRequestError(
            f'{label}超出系统大小上限',
            status_code=413,
            code='payload_too_large',
        )


def _idempotency_key(raw_key):
    if not raw_key:
        return str(uuid.uuid4())
    try:
        return str(uuid.UUID(str(raw_key)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ExecutionRequestError(
            'Idempotency-Key 必须是有效的 UUID',
            code='invalid_idempotency_key',
        ) from exc


def _limits(task_type):
    common = {
        'memory_mb': 128,
        'cpu_cores': 1,
        'pids': 16,
        'tmp_mb': 16,
        'output_bytes': 131072,
    }
    if task_type == TASK_TYPE_GRADE:
        return {**common, 'case_wall_seconds': 5, 'task_wall_seconds': 30}
    return {**common, 'wall_seconds': 10, 'task_wall_seconds': 12}


def _lock_user_and_check_capacity(user):
    CustomUser.objects.select_for_update().get(pk=user.pk)
    tasks = ExecutionTask.objects.filter(user=user)
    if tasks.filter(status=STATUS_RUNNING).count() >= settings.EXECUTION_USER_RUNNING_LIMIT:
        raise ExecutionRequestError(
            '你已有代码正在执行，请稍后再试',
            status_code=429,
            code='running_limit_reached',
        )
    if tasks.filter(status=STATUS_QUEUED).count() >= settings.EXECUTION_USER_QUEUED_LIMIT:
        raise ExecutionRequestError(
            '你的代码任务排队已满，请等待完成后再试',
            status_code=429,
            code='queue_limit_reached',
        )


def _existing_task(user, key, expected_hash):
    task = ExecutionTask.objects.filter(user=user, idempotency_key=key).first()
    if task and task.snapshot_hash != expected_hash:
        raise ExecutionRequestError(
            '同一 Idempotency-Key 不能用于不同请求',
            status_code=409,
            code='idempotency_conflict',
        )
    return task


def enqueue_run(*, user, code, stdin='', idempotency_key=None):
    _validate_text_size(code, 'EXECUTION_CODE_MAX_BYTES', '代码')
    _validate_text_size(stdin, 'EXECUTION_STDIN_MAX_BYTES', '标准输入')
    key = _idempotency_key(idempotency_key)
    digest = snapshot_digest({'task_type': TASK_TYPE_RUN, 'code': code, 'stdin': stdin})

    with transaction.atomic():
        existing = _existing_task(user, key, digest)
        if existing:
            return existing, False
        _lock_user_and_check_capacity(user)
        try:
            with transaction.atomic():
                task = ExecutionTask.objects.create(
                    user=user,
                    task_type=TASK_TYPE_RUN,
                    code=code,
                    stdin=stdin,
                    snapshot_hash=digest,
                    limits=_limits(TASK_TYPE_RUN),
                    idempotency_key=key,
                    expires_at=timezone.now() + timezone.timedelta(
                        seconds=settings.EXECUTION_QUEUE_TTL_SECONDS,
                    ),
                )
        except IntegrityError:
            task = _existing_task(user, key, digest)
            if not task:
                raise
            return task, False
    return task, True


def enqueue_grade(*, user, problem, code, idempotency_key=None):
    _validate_text_size(code, 'EXECUTION_CODE_MAX_BYTES', '代码')
    snapshot = build_test_snapshot(problem)
    key = _idempotency_key(idempotency_key)
    digest = snapshot_digest({
        'task_type': TASK_TYPE_GRADE,
        'problem_id': problem.problem_id,
        'code': code,
        'test_snapshot': snapshot,
    })

    with transaction.atomic():
        existing = _existing_task(user, key, digest)
        if existing:
            return existing, existing.submission, False
        _lock_user_and_check_capacity(user)
        try:
            with transaction.atomic():
                task = ExecutionTask.objects.create(
                    user=user,
                    problem=problem,
                    task_type=TASK_TYPE_GRADE,
                    code=code,
                    test_snapshot=snapshot,
                    snapshot_hash=digest,
                    limits=_limits(TASK_TYPE_GRADE),
                    idempotency_key=key,
                    expires_at=timezone.now() + timezone.timedelta(
                        seconds=settings.EXECUTION_QUEUE_TTL_SECONDS,
                    ),
                )
                submission = Submission.objects.create(
                    user=user,
                    problem=problem,
                    code=code,
                    score=None,
                    status='pending',
                    execution_task=task,
                )
        except IntegrityError:
            task = _existing_task(user, key, digest)
            if not task:
                raise
            return task, task.submission, False
    return task, submission, True
