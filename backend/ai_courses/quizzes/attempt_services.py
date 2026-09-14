"""Student visibility, attempt creation, recovery, and choice-answer persistence."""

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Max, Q
from django.utils import timezone

from users.models import CustomUser

from ..models import (
    AUDIENCE_ALL_SCHOOL,
    AUDIENCE_CLASS,
    AUDIENCE_GRADE_ALL,
    AIQuizAttempt,
    AIQuizSession,
)
from .services import AIQuizServiceError
from .snapshot import AIQuizSnapshotError, build_attempt_snapshot, student_snapshot_items


FINAL_ATTEMPT_STATUSES = (
    AIQuizAttempt.STATUS_SUBMITTED,
    AIQuizAttempt.STATUS_TIMED_OUT,
    AIQuizAttempt.STATUS_CLOSED,
    AIQuizAttempt.STATUS_RESET,
    AIQuizAttempt.STATUS_SUPERSEDED,
)


def _ensure_student(user):
    if (
        not user
        or not user.is_authenticated
        or not user.is_active
        or user.role != 'student'
    ):
        raise AIQuizServiceError(
            '当前账号没有学生作答权限',
            code='student_role_required', status_code=403,
        )
    if not user.grade or not user.class_num or not user.student_number:
        raise AIQuizServiceError(
            '学生身份信息不完整，请联系教师',
            code='student_identity_incomplete', status_code=403,
        )


def _audience_filter(user):
    return (
        Q(
            audience_rules__scope_type=AUDIENCE_ALL_SCHOOL,
            audience_rules__grade='', audience_rules__class_num='',
            audience_rules__is_active=True,
        )
        | Q(
            audience_rules__scope_type=AUDIENCE_GRADE_ALL,
            audience_rules__grade=user.grade, audience_rules__class_num='',
            audience_rules__is_active=True,
        )
        | Q(
            audience_rules__scope_type=AUDIENCE_CLASS,
            audience_rules__grade=user.grade,
            audience_rules__class_num=user.class_num,
            audience_rules__is_active=True,
        )
    )


def visible_ai_quizzes_for_student(queryset, user):
    _ensure_student(user)
    current_attempt = Q(
        attempts__user=user,
        attempts__current_marker=True,
    )
    open_and_visible = (
        Q(status=AIQuizSession.STATUS_OPEN, archived_at__isnull=True)
        & _audience_filter(user)
    )
    return queryset.filter(open_and_visible | current_attempt).distinct()


def _student_is_in_audience(user, session):
    return session.audience_rules.filter(is_active=True).filter(
        Q(scope_type=AUDIENCE_ALL_SCHOOL, grade='', class_num='')
        | Q(scope_type=AUDIENCE_GRADE_ALL, grade=user.grade, class_num='')
        | Q(scope_type=AUDIENCE_CLASS, grade=user.grade, class_num=user.class_num)
    ).exists()


def get_visible_ai_quiz_or_404(user, session_id, *, lock=False):
    _ensure_student(user)
    queryset = AIQuizSession.objects.filter(
        status=AIQuizSession.STATUS_OPEN,
        archived_at__isnull=True,
    )
    if lock:
        queryset = queryset.select_for_update()
    try:
        session = queryset.get(pk=session_id)
    except AIQuizSession.DoesNotExist as exc:
        raise AIQuizServiceError(
            '小测不存在', code='quiz_not_found', status_code=404,
        ) from exc
    has_current = AIQuizAttempt.objects.filter(
        user=user,
        session=session,
        current_marker=True,
        status__in=(AIQuizAttempt.STATUS_IN_PROGRESS, AIQuizAttempt.STATUS_SETTLING),
    ).exists()
    if not has_current and not _student_is_in_audience(user, session):
        raise AIQuizServiceError(
            '小测不存在', code='quiz_not_found', status_code=404,
        )
    return session


def _remaining_seconds(attempt, now=None):
    if not attempt.deadline_at:
        return None
    now = now or timezone.now()
    return max(0, int((attempt.deadline_at - now).total_seconds()))


def _deadline_passed(attempt, now=None):
    return bool(attempt.deadline_at and (now or timezone.now()) >= attempt.deadline_at)


def _mark_deadline_passed(attempt, now):
    if attempt.status == AIQuizAttempt.STATUS_IN_PROGRESS:
        attempt.status = AIQuizAttempt.STATUS_SETTLING
        attempt.final_reason = 'timed_out'
        attempt.settlement_requested_at = now
        attempt.save(update_fields=[
            'status', 'final_reason', 'settlement_requested_at', 'updated_at',
        ])


def _deadline_error(attempt_id):
    raise AIQuizServiceError(
        '作答时间已结束，试卷已锁定并等待结算',
        code='quiz_deadline_passed', status_code=410,
        attempt_id=attempt_id,
    )


def _snapshot_counts(snapshot):
    items = (snapshot or {}).get('items', [])
    return (
        sum(1 for item in items if item.get('type') == 'choice'),
        sum(1 for item in items if item.get('type') == 'programming'),
    )


def attempt_student_payload(attempt, *, created=False):
    now = timezone.now()
    snapshot = attempt.snapshot_json or {}
    session_data = snapshot.get('session') or {}
    choice_count, programming_count = _snapshot_counts(snapshot)
    return {
        'attempt_id': attempt.pk,
        'created': created,
        'status': attempt.status,
        'revision': attempt.answer_revision,
        'server_time': now,
        'started_at': attempt.started_at,
        'deadline_at': attempt.deadline_at,
        'remaining_seconds': _remaining_seconds(attempt, now),
        'quiz': {
            'id': attempt.session_id,
            'title': session_data.get('title') or attempt.session.title,
            'choice_count': choice_count,
            'programming_count': programming_count,
            'total_points': session_data.get('total_points', '100.0'),
            'time_limit': session_data.get('time_limit'),
            'blueprint_hash': snapshot.get('blueprint_hash', ''),
        },
        'items': student_snapshot_items(snapshot),
        'saved_answers': attempt.answers_json or {},
    }


def _create_attempt_locked(user, session, now):
    try:
        snapshot = build_attempt_snapshot(session)
    except AIQuizSnapshotError as exc:
        status_code = 409 if exc.code == 'quiz_pool_insufficient' else 500
        raise AIQuizServiceError(
            exc.message, code=exc.code, status_code=status_code,
        ) from exc
    latest_no = AIQuizAttempt.objects.filter(
        user=user, session=session,
    ).aggregate(value=Max('attempt_no'))['value'] or 0
    time_limit = (snapshot.get('session') or {}).get('time_limit')
    deadline = now + timedelta(minutes=time_limit) if time_limit else None
    return AIQuizAttempt.objects.create(
        user=user,
        session=session,
        status=AIQuizAttempt.STATUS_IN_PROGRESS,
        attempt_no=latest_no + 1,
        current_marker=True,
        snapshot_version=1,
        snapshot_json=snapshot,
        answers_json={},
        answer_revision=0,
        grade=user.grade,
        class_num=user.class_num,
        student_number=user.student_number,
        started_at=now,
        deadline_at=deadline,
    )


def start_or_resume_attempt(user, session_id):
    _ensure_student(user)
    expired_attempt_id = None
    try:
        with transaction.atomic():
            CustomUser.objects.select_for_update().get(pk=user.pk)
            session = get_visible_ai_quiz_or_404(user, session_id, lock=True)
            attempt = AIQuizAttempt.objects.select_for_update().filter(
                user=user, session=session, current_marker=True,
            ).first()
            now = timezone.now()
            if attempt:
                if attempt.status == AIQuizAttempt.STATUS_IN_PROGRESS:
                    if _deadline_passed(attempt, now):
                        _mark_deadline_passed(attempt, now)
                        expired_attempt_id = attempt.pk
                    else:
                        return attempt, False
                elif attempt.status == AIQuizAttempt.STATUS_SETTLING:
                    raise AIQuizServiceError(
                        '本次小测正在结算', code='attempt_not_active', status_code=409,
                        attempt_id=attempt.pk,
                    )
                if expired_attempt_id is None:
                    attempt.current_marker = None
                    if attempt.status not in FINAL_ATTEMPT_STATUSES:
                        attempt.status = AIQuizAttempt.STATUS_SUPERSEDED
                    attempt.save(update_fields=['current_marker', 'status', 'updated_at'])

            if expired_attempt_id is None:
                if not _student_is_in_audience(user, session):
                    raise AIQuizServiceError(
                        '小测不存在', code='quiz_not_found', status_code=404,
                    )
                return _create_attempt_locked(user, session, now), True
    except IntegrityError:
        attempt = AIQuizAttempt.objects.filter(
            user=user, session_id=session_id, current_marker=True,
        ).first()
        if attempt:
            return attempt, False
        raise
    if expired_attempt_id is not None:
        _deadline_error(expired_attempt_id)


def get_current_attempt(user, session_id):
    _ensure_student(user)
    try:
        attempt = AIQuizAttempt.objects.select_related('session').get(
            user=user,
            session_id=session_id,
            current_marker=True,
        )
    except AIQuizAttempt.DoesNotExist as exc:
        raise AIQuizServiceError(
            '作答不存在', code='attempt_not_found', status_code=404,
        ) from exc
    if (
        attempt.session.status != AIQuizSession.STATUS_OPEN
        or attempt.session.archived_at is not None
    ):
        raise AIQuizServiceError(
            '小测当前未开放', code='quiz_not_open', status_code=409,
        )
    now = timezone.now()
    if attempt.status == AIQuizAttempt.STATUS_IN_PROGRESS and _deadline_passed(attempt, now):
        with transaction.atomic():
            locked = AIQuizAttempt.objects.select_for_update().get(pk=attempt.pk)
            _mark_deadline_passed(locked, now)
        _deadline_error(attempt.pk)
    if attempt.status != AIQuizAttempt.STATUS_IN_PROGRESS:
        raise AIQuizServiceError(
            '本次作答不可继续', code='attempt_not_active', status_code=409,
            attempt_id=attempt.pk,
        )
    return attempt


def _normalize_answers(attempt, answers):
    if not isinstance(answers, dict):
        raise AIQuizServiceError('答案格式不正确', code='invalid_answers')
    valid_ids = {
        item['item_id']
        for item in (attempt.snapshot_json or {}).get('items', [])
        if item.get('type') == 'choice'
    }
    normalized = {}
    for raw_item_id, raw_answer in answers.items():
        item_id = str(raw_item_id)
        if item_id not in valid_ids:
            raise AIQuizServiceError(
                '答案包含不属于本次试卷的选择题', code='unknown_quiz_item',
            )
        if raw_answer in (None, ''):
            continue
        answer = str(raw_answer).upper()
        if answer not in ('A', 'B', 'C', 'D'):
            raise AIQuizServiceError(
                '答案选项必须为 A、B、C 或 D', code='invalid_option',
            )
        normalized[item_id] = answer
    return normalized


def save_choice_answers(user, session_id, attempt_id, revision, answers):
    _ensure_student(user)
    expired_attempt_id = None
    with transaction.atomic():
        try:
            attempt = AIQuizAttempt.objects.select_for_update().select_related('session').get(
                pk=attempt_id,
                user=user,
                session_id=session_id,
                current_marker=True,
            )
        except AIQuizAttempt.DoesNotExist as exc:
            raise AIQuizServiceError(
                '作答不存在', code='attempt_not_found', status_code=404,
            ) from exc
        now = timezone.now()
        if (
            attempt.session.status != AIQuizSession.STATUS_OPEN
            or attempt.session.archived_at is not None
        ):
            raise AIQuizServiceError(
                '小测当前未开放', code='quiz_not_open', status_code=409,
            )
        if attempt.status == AIQuizAttempt.STATUS_IN_PROGRESS and _deadline_passed(attempt, now):
            _mark_deadline_passed(attempt, now)
            expired_attempt_id = attempt.pk
        elif attempt.status != AIQuizAttempt.STATUS_IN_PROGRESS:
            raise AIQuizServiceError(
                '本次作答不可修改', code='attempt_not_active', status_code=409,
            )
        elif revision != attempt.answer_revision:
            raise AIQuizServiceError(
                '作答版本已变化，请重新加载',
                code='attempt_revision_conflict', status_code=409,
                current_revision=attempt.answer_revision,
            )
        else:
            normalized = _normalize_answers(attempt, answers)
            attempt.answers_json = normalized
            attempt.answer_revision += 1
            attempt.save(update_fields=['answers_json', 'answer_revision', 'updated_at'])
    if expired_attempt_id is not None:
        _deadline_error(expired_attempt_id)
    return attempt


def student_quiz_list(user):
    sessions = list(visible_ai_quizzes_for_student(
        AIQuizSession.objects.all(), user,
    ).order_by('-opened_at', '-id'))
    attempts = {
        attempt.session_id: attempt
        for attempt in AIQuizAttempt.objects.filter(
            user=user,
            session_id__in=[session.pk for session in sessions],
            current_marker=True,
        ).select_related('session')
    }
    best_scores = {
        row['session_id']: row['best_score']
        for row in AIQuizAttempt.objects.filter(
            user=user, session_id__in=[session.pk for session in sessions],
            total_score__isnull=False,
        ).values('session_id').annotate(best_score=Max('total_score'))
    }
    now = timezone.now()
    result = []
    for session in sessions:
        attempt = attempts.get(session.pk)
        config = (session.blueprint_json or {}).get('session') or {}
        programming_count = len((session.blueprint_json or {}).get('programming_items') or [])
        if not attempt:
            action = 'start'
            attempt_status = 'not_started'
        elif attempt.status == AIQuizAttempt.STATUS_IN_PROGRESS and _deadline_passed(attempt, now):
            action = 'settling'
            attempt_status = AIQuizAttempt.STATUS_SETTLING
        elif attempt.status == AIQuizAttempt.STATUS_IN_PROGRESS:
            action = 'continue'
            attempt_status = attempt.status
        elif attempt.status == AIQuizAttempt.STATUS_SETTLING:
            action = 'settling'
            attempt_status = attempt.status
        elif attempt.status in FINAL_ATTEMPT_STATUSES:
            action = 'result'
            attempt_status = attempt.status
        else:
            action = 'restart'
            attempt_status = attempt.status
        result.append({
            'id': session.pk,
            'title': session.title,
            'content_grade': session.content_grade,
            'choice_count': config.get('choice_question_count', 0),
            'programming_count': programming_count,
            'total_points': '100.0',
            'time_limit': config.get('time_limit'),
            'status': session.status,
            'attempt_id': attempt.pk if attempt else None,
            'attempt_status': attempt_status,
            'action': action,
            'remaining_seconds': _remaining_seconds(attempt, now) if attempt else None,
            'latest_score': attempt.total_score if attempt else None,
            'best_score': best_scores.get(session.pk),
        })
    return result
