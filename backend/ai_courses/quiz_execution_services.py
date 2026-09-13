"""Programming execution bound to an active, immutable AI quiz attempt."""

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from execution.constants import ACTIVE_STATUSES
from execution.models import ExecutionTask
from execution.services import enqueue_quiz_grade, enqueue_quiz_run
from execution.snapshots import snapshot_digest
from users.models import CustomUser

from .models import AIQuizAttempt, AIQuizSession, Problem, Submission
from .quiz_attempt_services import (
    _deadline_error,
    _deadline_passed,
    _ensure_student,
    _mark_deadline_passed,
    get_current_attempt,
)
from .quiz_services import AIQuizServiceError, blueprint_digest


def _programming_context(attempt, item_id):
    snapshot = attempt.snapshot_json or {}
    blueprint = attempt.session.blueprint_json or {}
    if (
        snapshot.get('blueprint_hash') != attempt.session.blueprint_hash
        or blueprint_digest(blueprint) != attempt.session.blueprint_hash
    ):
        raise AIQuizServiceError(
            '小测试卷快照校验失败，请联系教师',
            code='quiz_blueprint_invalid', status_code=409,
        )
    attempt_item = next((
        item for item in snapshot.get('items', [])
        if item.get('item_id') == item_id and item.get('type') == 'programming'
    ), None)
    blueprint_item = next((
        item for item in blueprint.get('programming_items', [])
        if item.get('item_id') == item_id
    ), None)
    if not attempt_item or not blueprint_item:
        raise AIQuizServiceError(
            '编程题不属于本次试卷', code='unknown_quiz_item', status_code=404,
        )
    if (
        attempt_item.get('source_problem_id') != blueprint_item.get('source_problem_id')
        or attempt_item.get('test_snapshot_hash') != blueprint_item.get('test_snapshot_hash')
        or snapshot_digest(blueprint_item.get('test_snapshot'))
        != blueprint_item.get('test_snapshot_hash')
    ):
        raise AIQuizServiceError(
            '小测编程题快照校验失败，请联系教师',
            code='quiz_test_snapshot_invalid', status_code=409,
        )
    try:
        problem = Problem.objects.get(
            problem_id=blueprint_item['source_problem_id'], course='ai',
        )
    except Problem.DoesNotExist as exc:
        raise AIQuizServiceError(
            '小测编程题来源不存在，请联系教师',
            code='quiz_problem_unavailable', status_code=409,
        ) from exc
    return attempt_item, blueprint_item, problem


def _locked_active_context(user, session_id, attempt_id, item_id):
    _ensure_student(user)
    CustomUser.objects.select_for_update().get(pk=user.pk)
    try:
        session = AIQuizSession.objects.select_for_update().get(pk=session_id)
        attempt = AIQuizAttempt.objects.select_for_update().get(
            pk=attempt_id,
            user=user,
            session=session,
            current_marker=True,
        )
    except (AIQuizSession.DoesNotExist, AIQuizAttempt.DoesNotExist) as exc:
        raise AIQuizServiceError(
            '作答不存在', code='attempt_not_found', status_code=404,
        ) from exc
    attempt.session = session
    if session.status != AIQuizSession.STATUS_OPEN or session.archived_at is not None:
        raise AIQuizServiceError(
            '小测当前未开放', code='quiz_not_open', status_code=409,
        )
    now = timezone.now()
    if attempt.status == AIQuizAttempt.STATUS_IN_PROGRESS and _deadline_passed(attempt, now):
        _mark_deadline_passed(attempt, now)
        return None, attempt.pk
    if attempt.status != AIQuizAttempt.STATUS_IN_PROGRESS:
        raise AIQuizServiceError(
            '本次作答不可继续', code='attempt_not_active', status_code=409,
            attempt_id=attempt.pk,
        )
    return (attempt, *_programming_context(attempt, item_id)), None


def programming_item_payload(user, session_id, item_id):
    attempt = get_current_attempt(user, session_id)
    attempt_item, _blueprint_item, _problem = _programming_context(attempt, item_id)
    best_score = Submission.objects.filter(
        user=user,
        quiz_attempt=attempt,
        quiz_item_id=item_id,
        counts_for_quiz=True,
        score__isnull=False,
    ).aggregate(value=Max('score'))['value']
    return {
        'attempt_id': attempt.pk,
        'item_id': item_id,
        'type': 'programming',
        'position': attempt_item.get('position'),
        'title': attempt_item.get('title', ''),
        'description': attempt_item.get('description', ''),
        'template_code': attempt_item.get('template_code', ''),
        'points': attempt_item.get('points', '0.0'),
        'best_score': best_score,
    }


def enqueue_attempt_run(user, session_id, attempt_id, item_id, code, stdin, idempotency_key):
    expired_attempt_id = None
    with transaction.atomic():
        context, expired_attempt_id = _locked_active_context(
            user, session_id, attempt_id, item_id,
        )
        if context:
            attempt, _attempt_item, _blueprint_item, problem = context
            result = enqueue_quiz_run(
                user=user,
                quiz_attempt=attempt,
                quiz_item_id=item_id,
                problem=problem,
                code=code,
                stdin=stdin,
                idempotency_key=idempotency_key,
            )
    if expired_attempt_id is not None:
        _deadline_error(expired_attempt_id)
    return result


def enqueue_attempt_grade(user, session_id, attempt_id, item_id, code, idempotency_key):
    expired_attempt_id = None
    with transaction.atomic():
        context, expired_attempt_id = _locked_active_context(
            user, session_id, attempt_id, item_id,
        )
        if context:
            attempt, _attempt_item, blueprint_item, problem = context
            result = enqueue_quiz_grade(
                user=user,
                quiz_attempt=attempt,
                quiz_item_id=item_id,
                problem=problem,
                code=code,
                test_snapshot=blueprint_item['test_snapshot'],
                test_snapshot_hash=blueprint_item['test_snapshot_hash'],
                idempotency_key=idempotency_key,
            )
    if expired_attempt_id is not None:
        _deadline_error(expired_attempt_id)
    return result


def active_attempt_execution(user, session_id, attempt_id, item_id, task_type):
    attempt = get_current_attempt(user, session_id)
    if attempt.pk != attempt_id:
        raise AIQuizServiceError(
            '作答不存在', code='attempt_not_found', status_code=404,
        )
    _programming_context(attempt, item_id)
    return ExecutionTask.objects.filter(
        user=user,
        quiz_attempt=attempt,
        quiz_item_id=item_id,
        task_type=task_type,
        status__in=ACTIVE_STATUSES,
    ).select_related('submission').order_by('-created_at').first()
