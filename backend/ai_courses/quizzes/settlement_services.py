"""Idempotent settlement, scoring, reset, and regrade for AI quiz attempts."""

from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from execution.constants import (
    ACTIVE_STATUSES,
    STATUS_CANCELLED,
    STATUS_SYSTEM_ERROR,
    TASK_TYPE_GRADE,
)
from execution.models import ExecutionTask
from execution.services import enqueue_quiz_grade
from users.models import CustomUser

from ..models import AIQuizAttempt, AIQuizManagementAudit, AIQuizSession, Problem, Submission
from .attempt_services import _ensure_student, _normalize_answers
from .services import AIQuizServiceError, blueprint_digest, scoped_quizzes


ONE_DECIMAL = Decimal('0.1')
FINAL_STATUS_BY_REASON = {
    'submitted': AIQuizAttempt.STATUS_SUBMITTED,
    'timed_out': AIQuizAttempt.STATUS_TIMED_OUT,
    'closed': AIQuizAttempt.STATUS_CLOSED,
}


def _points(value):
    try:
        return Decimal(str(value or '0'))
    except Exception as exc:
        raise AIQuizServiceError(
            '小测分值快照无效，请联系教师',
            code='quiz_blueprint_invalid', status_code=409,
        ) from exc


def _quantize(value):
    return value.quantize(ONE_DECIMAL, rounding=ROUND_HALF_UP)


def _active_grade_tasks(attempt):
    return ExecutionTask.objects.filter(
        quiz_attempt=attempt,
        task_type=TASK_TYPE_GRADE,
        status__in=ACTIVE_STATUSES,
        submission__counts_for_quiz=True,
    )


def _snapshot_items(attempt, item_type):
    return [
        item for item in (attempt.snapshot_json or {}).get('items', [])
        if item.get('type') == item_type
    ]


def _best_submission(attempt, item_id):
    return Submission.objects.filter(
        quiz_attempt=attempt,
        quiz_item_id=item_id,
        counts_for_quiz=True,
        score__isnull=False,
    ).select_related('execution_task').order_by(
        '-score', F('execution_task__finished_at').asc(nulls_last=True), 'submitted_at', 'id',
    ).first()


def _item_has_system_issue(attempt, item_id):
    return ExecutionTask.objects.filter(
        quiz_attempt=attempt,
        quiz_item_id=item_id,
        task_type=TASK_TYPE_GRADE,
        status__in=(STATUS_SYSTEM_ERROR, STATUS_CANCELLED),
        submission__counts_for_quiz=True,
    ).exists()


@transaction.atomic
def finalize_attempt(attempt_id):
    """Finalize once every accepted grade task is terminal; safe to call repeatedly."""
    try:
        attempt = AIQuizAttempt.objects.select_for_update().select_related('session').get(
            pk=attempt_id,
        )
    except AIQuizAttempt.DoesNotExist as exc:
        raise AIQuizServiceError(
            '作答不存在', code='attempt_not_found', status_code=404,
        ) from exc
    if attempt.status != AIQuizAttempt.STATUS_SETTLING:
        return attempt
    if _active_grade_tasks(attempt).exists():
        return attempt

    snapshot = attempt.snapshot_json or {}
    if (
        snapshot.get('blueprint_hash') != attempt.session.blueprint_hash
        or blueprint_digest(attempt.session.blueprint_json or {}) != attempt.session.blueprint_hash
    ):
        raise AIQuizServiceError(
            '小测试卷快照校验失败，请联系教师',
            code='quiz_blueprint_invalid', status_code=409,
        )

    choice_items = _snapshot_items(attempt, 'choice')
    correct_count = sum(
        1 for item in choice_items
        if (attempt.answers_json or {}).get(item.get('item_id'))
        == item.get('correct_display_option')
    )
    choice_total = _points((snapshot.get('session') or {}).get('choice_points'))
    choice_score = (
        _quantize(choice_total * Decimal(correct_count) / Decimal(len(choice_items)))
        if choice_items else Decimal('0.0')
    )

    programming_score = Decimal('0')
    issue_count = 0
    for item in _snapshot_items(attempt, 'programming'):
        best = _best_submission(attempt, item.get('item_id'))
        if best is not None:
            programming_score += _points(item.get('points')) * Decimal(str(best.score)) / Decimal('100')
        elif _item_has_system_issue(attempt, item.get('item_id')):
            issue_count += 1
    programming_score = _quantize(programming_score)
    total_score = _quantize(choice_score + programming_score)

    final_status = FINAL_STATUS_BY_REASON.get(attempt.final_reason)
    if final_status is None:
        raise AIQuizServiceError(
            '作答结算原因无效', code='invalid_settlement_reason', status_code=409,
        )
    attempt.status = final_status
    attempt.choice_score = choice_score
    attempt.programming_score = programming_score
    attempt.total_score = total_score
    attempt.correct_count = correct_count
    attempt.choice_count = len(choice_items)
    attempt.grading_issue_count = issue_count
    attempt.settled_at = timezone.now()
    attempt.result_revision += 1
    attempt.save(update_fields=[
        'status', 'choice_score', 'programming_score', 'total_score',
        'correct_count', 'choice_count', 'grading_issue_count', 'settled_at',
        'result_revision', 'updated_at',
    ])
    return attempt


def request_settlement(
    *, user, session_id, attempt_id, reason='submitted',
    final_answers=None, revision=None,
):
    """Lock the paper immediately, then finalize now or after accepted grading finishes."""
    _ensure_student(user)
    if reason not in FINAL_STATUS_BY_REASON:
        raise AIQuizServiceError('结算原因无效', code='invalid_settlement_reason')
    with transaction.atomic():
        CustomUser.objects.select_for_update().get(pk=user.pk)
        try:
            session = AIQuizSession.objects.select_for_update().get(pk=session_id)
            attempt = AIQuizAttempt.objects.select_for_update().get(
                pk=attempt_id, user=user, session=session, current_marker=True,
            )
        except (AIQuizSession.DoesNotExist, AIQuizAttempt.DoesNotExist) as exc:
            raise AIQuizServiceError(
                '作答不存在', code='attempt_not_found', status_code=404,
            ) from exc
        if attempt.status in FINAL_STATUS_BY_REASON.values():
            return attempt
        if attempt.status == AIQuizAttempt.STATUS_SETTLING:
            pass
        elif attempt.status != AIQuizAttempt.STATUS_IN_PROGRESS:
            raise AIQuizServiceError(
                '本次作答不可交卷', code='attempt_not_active', status_code=409,
            )
        else:
            now = timezone.now()
            effective_reason = reason
            if reason == 'submitted':
                if session.status != AIQuizSession.STATUS_OPEN or session.archived_at is not None:
                    raise AIQuizServiceError(
                        '小测当前未开放', code='quiz_not_open', status_code=409,
                    )
                if attempt.deadline_at and now >= attempt.deadline_at:
                    effective_reason = 'timed_out'
                elif final_answers is not None:
                    if revision != attempt.answer_revision:
                        raise AIQuizServiceError(
                            '作答版本已变化，请重新加载',
                            code='attempt_revision_conflict', status_code=409,
                            current_revision=attempt.answer_revision,
                        )
                    attempt.answers_json = _normalize_answers(attempt, final_answers)
                    attempt.answer_revision += 1
            attempt.status = AIQuizAttempt.STATUS_SETTLING
            attempt.final_reason = effective_reason
            attempt.settlement_requested_at = now
            attempt.save(update_fields=[
                'status', 'final_reason', 'settlement_requested_at',
                'answers_json', 'answer_revision', 'updated_at',
            ])
    return finalize_attempt(attempt.pk)


def request_system_settlement(attempt_id, reason):
    """Internal timeout/close variant that never trusts student request data."""
    if reason not in ('timed_out', 'closed'):
        raise AIQuizServiceError('结算原因无效', code='invalid_settlement_reason')
    with transaction.atomic():
        try:
            attempt = AIQuizAttempt.objects.select_for_update().get(pk=attempt_id)
        except AIQuizAttempt.DoesNotExist:
            return None
        if attempt.status in FINAL_STATUS_BY_REASON.values():
            return attempt
        if attempt.status == AIQuizAttempt.STATUS_IN_PROGRESS:
            attempt.status = AIQuizAttempt.STATUS_SETTLING
            attempt.final_reason = reason
            attempt.settlement_requested_at = timezone.now()
            attempt.save(update_fields=[
                'status', 'final_reason', 'settlement_requested_at', 'updated_at',
            ])
        elif attempt.status != AIQuizAttempt.STATUS_SETTLING:
            return attempt
    return finalize_attempt(attempt.pk)


def settle_session_attempts(session_id, reason='closed'):
    attempt_ids = list(AIQuizAttempt.objects.filter(
        session_id=session_id,
        status=AIQuizAttempt.STATUS_IN_PROGRESS,
        current_marker=True,
    ).values_list('pk', flat=True))
    for attempt_id in attempt_ids:
        request_system_settlement(attempt_id, reason)
    return len(attempt_ids)


def settle_due_attempts(*, now=None):
    now = now or timezone.now()
    expired_ids = list(AIQuizAttempt.objects.filter(
        status=AIQuizAttempt.STATUS_IN_PROGRESS,
        current_marker=True,
        deadline_at__isnull=False,
        deadline_at__lte=now,
    ).values_list('pk', flat=True))
    for attempt_id in expired_ids:
        request_system_settlement(attempt_id, 'timed_out')
    settling_ids = list(AIQuizAttempt.objects.filter(
        status=AIQuizAttempt.STATUS_SETTLING,
    ).values_list('pk', flat=True))
    for attempt_id in settling_ids:
        finalize_attempt(attempt_id)
    return {'expired_requested': len(expired_ids), 'settling_checked': len(settling_ids)}


def maybe_finalize_attempt(task_id):
    task = ExecutionTask.objects.filter(pk=task_id).values(
        'quiz_attempt_id', 'task_type',
    ).first()
    if task and task['quiz_attempt_id'] and task['task_type'] == TASK_TYPE_GRADE:
        return finalize_attempt(task['quiz_attempt_id'])
    return None


def _attempt_for_result(user, session_id):
    _ensure_student(user)
    attempt = AIQuizAttempt.objects.select_related('session').filter(
        user=user,
        session_id=session_id,
    ).exclude(status=AIQuizAttempt.STATUS_RESET).order_by('-current_marker', '-attempt_no').first()
    if attempt is None:
        raise AIQuizServiceError(
            '作答不存在', code='attempt_not_found', status_code=404,
        )
    return attempt


def _attempt_result_payload(attempt):
    snapshot = attempt.snapshot_json or {}
    choice_details = []
    for item in _snapshot_items(attempt, 'choice'):
        selected = (attempt.answers_json or {}).get(item.get('item_id'))
        choice_details.append({
            'item_id': item.get('item_id'),
            'position': item.get('position'),
            'text': item.get('text', ''),
            'options': item.get('options') or {},
            'selected_option': selected,
            'correct_option': item.get('correct_display_option'),
            'is_correct': selected == item.get('correct_display_option'),
            'explanation': item.get('explanation', ''),
        })
    programming_details = []
    for item in _snapshot_items(attempt, 'programming'):
        best = _best_submission(attempt, item.get('item_id'))
        submission_count = Submission.objects.filter(
            quiz_attempt=attempt,
            quiz_item_id=item.get('item_id'),
            counts_for_quiz=True,
            score__isnull=False,
        ).count()
        has_issue = best is None and _item_has_system_issue(attempt, item.get('item_id'))
        raw_score = Decimal(str(best.score)) if best else Decimal('0')
        earned = _quantize(_points(item.get('points')) * raw_score / Decimal('100'))
        programming_details.append({
            'item_id': item.get('item_id'),
            'position': item.get('position'),
            'title': item.get('title', ''),
            'points': item.get('points', '0.0'),
            'best_score': float(best.score) if best else None,
            'earned_points': format(earned, '.1f'),
            'best_submission_id': best.pk if best else None,
            'submission_count': submission_count,
            'status': 'system_issue' if has_issue else ('scored' if best else 'not_submitted'),
        })
    session_data = snapshot.get('session') or {}
    return {
        'attempt_id': attempt.pk,
        'attempt_no': attempt.attempt_no,
        'status': attempt.status,
        'final_reason': attempt.final_reason,
        'result_revision': attempt.result_revision,
        'started_at': attempt.started_at,
        'deadline_at': attempt.deadline_at,
        'settlement_requested_at': attempt.settlement_requested_at,
        'settled_at': attempt.settled_at,
        'quiz': {
            'id': attempt.session_id,
            'title': session_data.get('title') or attempt.session.title,
            'total_points': session_data.get('total_points', '100.0'),
        },
        'scores': {
            'choice': format(attempt.choice_score, '.1f') if attempt.choice_score is not None else None,
            'programming': format(attempt.programming_score, '.1f') if attempt.programming_score is not None else None,
            'total': format(attempt.total_score, '.1f') if attempt.total_score is not None else None,
        },
        'choice_summary': {
            'correct_count': attempt.correct_count,
            'question_count': attempt.choice_count,
        },
        'grading_issue_count': attempt.grading_issue_count,
        'can_retry': (
            attempt.session.status == AIQuizSession.STATUS_OPEN
            and attempt.session.archived_at is None
        ),
        'choice_items': choice_details if attempt.status in FINAL_STATUS_BY_REASON.values() else [],
        'programming_items': programming_details if attempt.status in FINAL_STATUS_BY_REASON.values() else [],
    }


def get_student_result(user, session_id):
    attempt = _attempt_for_result(user, session_id)
    now = timezone.now()
    if (
        attempt.status == AIQuizAttempt.STATUS_IN_PROGRESS
        and attempt.deadline_at
        and now >= attempt.deadline_at
    ):
        attempt = request_system_settlement(attempt.pk, 'timed_out')
    elif attempt.status == AIQuizAttempt.STATUS_SETTLING:
        attempt = finalize_attempt(attempt.pk)
    return _attempt_result_payload(attempt)


def student_attempt_history(user, session_id):
    _ensure_student(user)
    attempts = AIQuizAttempt.objects.filter(
        user=user, session_id=session_id,
    ).order_by('-attempt_no')
    if not attempts.exists():
        raise AIQuizServiceError(
            '作答不存在', code='attempt_not_found', status_code=404,
        )
    return [
        {
            'attempt_id': attempt.pk,
            'attempt_no': attempt.attempt_no,
            'status': attempt.status,
            'final_reason': attempt.final_reason,
            'total_score': format(attempt.total_score, '.1f') if attempt.total_score is not None else None,
            'grading_issue_count': attempt.grading_issue_count,
            'started_at': attempt.started_at,
            'settled_at': attempt.settled_at,
            'result_revision': attempt.result_revision,
        }
        for attempt in attempts
    ]


@transaction.atomic
def reset_attempt(*, actor, session_id, attempt_id, reason):
    try:
        scoped_quizzes(actor, include_archived=True).get(pk=session_id)
        session = AIQuizSession.objects.select_for_update().get(pk=session_id)
        attempt = AIQuizAttempt.objects.select_for_update().get(
            pk=attempt_id, session=session, current_marker=True,
        )
    except (AIQuizSession.DoesNotExist, AIQuizAttempt.DoesNotExist) as exc:
        raise AIQuizServiceError(
            '作答不存在', code='attempt_not_found', status_code=404,
        ) from exc
    if session.status != AIQuizSession.STATUS_OPEN or session.archived_at is not None:
        raise AIQuizServiceError(
            '只有开放中的小测可以重置作答', code='quiz_not_open', status_code=409,
        )
    clean_reason = (reason or '').strip()
    if not clean_reason:
        raise AIQuizServiceError('请填写重置原因', code='reset_reason_required')
    attempt.status = AIQuizAttempt.STATUS_RESET
    attempt.current_marker = None
    attempt.reset_at = timezone.now()
    attempt.reset_by = actor
    attempt.reset_reason = clean_reason
    attempt.save(update_fields=[
        'status', 'current_marker', 'reset_at', 'reset_by', 'reset_reason', 'updated_at',
    ])
    AIQuizManagementAudit.objects.create(
        event_type='attempt_reset', outcome='success', actor_user_id=actor.pk,
        object_type='attempt', object_id=str(attempt.pk),
        after_summary={'session_id': session.pk, 'reason': clean_reason},
    )
    return attempt


@transaction.atomic
def regrade_quiz_item(*, actor, session_id, attempt_id, item_id, idempotency_key=None):
    try:
        scoped_quizzes(actor, include_archived=True).get(pk=session_id)
        session = AIQuizSession.objects.select_for_update().get(pk=session_id)
        attempt = AIQuizAttempt.objects.select_for_update().get(
            pk=attempt_id, session=session,
        )
    except (AIQuizSession.DoesNotExist, AIQuizAttempt.DoesNotExist) as exc:
        raise AIQuizServiceError(
            '作答不存在', code='attempt_not_found', status_code=404,
        ) from exc
    if idempotency_key:
        existing = ExecutionTask.objects.filter(
            user=attempt.user,
            quiz_attempt=attempt,
            quiz_item_id=item_id,
            idempotency_key=str(idempotency_key),
            submission__regrade_of__isnull=False,
        ).select_related('submission').first()
        if existing is not None:
            return existing, existing.submission, False
    if attempt.grading_issue_count <= 0 or attempt.status not in FINAL_STATUS_BY_REASON.values():
        raise AIQuizServiceError(
            '该作答当前没有可重评的系统异常',
            code='regrade_not_allowed', status_code=409,
        )
    blueprint_item = next((
        item for item in (session.blueprint_json or {}).get('programming_items', [])
        if item.get('item_id') == item_id
    ), None)
    if blueprint_item is None:
        raise AIQuizServiceError(
            '编程题不属于本次试卷', code='unknown_quiz_item', status_code=404,
        )
    failed = Submission.objects.filter(
        quiz_attempt=attempt,
        quiz_item_id=item_id,
        execution_task__status__in=(STATUS_SYSTEM_ERROR, STATUS_CANCELLED),
    ).select_related('execution_task').order_by('-submitted_at', '-id').first()
    if failed is None or _best_submission(attempt, item_id) is not None:
        raise AIQuizServiceError(
            '该题当前不允许重评', code='regrade_not_allowed', status_code=409,
        )
    try:
        problem = Problem.objects.get(problem_id=blueprint_item['source_problem_id'], course='ai')
    except Problem.DoesNotExist as exc:
        raise AIQuizServiceError(
            '小测编程题来源不存在', code='quiz_problem_unavailable', status_code=409,
        ) from exc
    task, submission, created = enqueue_quiz_grade(
        user=attempt.user,
        quiz_attempt=attempt,
        quiz_item_id=item_id,
        problem=problem,
        code=failed.code,
        test_snapshot=blueprint_item['test_snapshot'],
        test_snapshot_hash=blueprint_item['test_snapshot_hash'],
        idempotency_key=idempotency_key,
    )
    if created:
        submission.regrade_of = failed
        submission.save(update_fields=['regrade_of'])
        attempt.status = AIQuizAttempt.STATUS_SETTLING
        attempt.settled_at = None
        attempt.save(update_fields=['status', 'settled_at', 'updated_at'])
        AIQuizManagementAudit.objects.create(
            event_type='attempt_regrade', outcome='success', actor_user_id=actor.pk,
            object_type='attempt', object_id=str(attempt.pk),
            after_summary={'session_id': session.pk, 'item_id': item_id},
        )
    return task, submission, created
