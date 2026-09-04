import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from .models import QuizSession, QuizSubmission
from .quiz_snapshot import SnapshotBuildError, build_quiz_snapshot


GRACE_SECONDS = 5
SETTLED_STATUSES = (
    QuizSubmission.STATUS_SUBMITTED,
    QuizSubmission.STATUS_TIMED_OUT,
)


class QuizServiceError(Exception):
    def __init__(self, code, message, http_status=400, **extra):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.extra = extra


def canonical_answers(answers):
    return json.dumps(answers, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def ensure_student(user):
    if not user.is_authenticated or user.role != 'student':
        raise QuizServiceError('student_role_required', '当前账号没有学生作答权限', 403)


def ensure_student_can_access(user, session):
    ensure_student(user)
    visible_grades = session.visible_grades or []
    if visible_grades and user.grade not in visible_grades:
        raise QuizServiceError('quiz_grade_forbidden', '无权限访问该小测', 403)
    visible_classes = {str(value) for value in (session.visible_classes or [])}
    if visible_classes and str(user.class_num or '') not in visible_classes:
        raise QuizServiceError('quiz_class_forbidden', '无权限访问该小测', 403)


def _deadline_with_grace(attempt):
    if not attempt.deadline_at:
        return None
    return attempt.deadline_at + timedelta(seconds=GRACE_SECONDS)


def _is_past_grace(attempt, now):
    end = _deadline_with_grace(attempt)
    return bool(end and now > end)


def _remaining_seconds(attempt, now=None):
    if not attempt.deadline_at:
        return None
    now = now or timezone.now()
    return max(0, int((attempt.deadline_at - now).total_seconds()))


def _normalize_answers(attempt, answers):
    if not isinstance(answers, dict):
        raise QuizServiceError('invalid_answers', '答案格式不正确', 400)
    snapshot_items = (attempt.snapshot_json or {}).get('questions', [])
    valid_ids = {item['item_id'] for item in snapshot_items}
    normalized = {}
    for raw_item_id, raw_answer in answers.items():
        item_id = str(raw_item_id)
        if item_id not in valid_ids:
            raise QuizServiceError('unknown_quiz_item', '答案包含不属于本次试卷的题目', 400)
        if raw_answer in (None, ''):
            continue
        answer = str(raw_answer).upper()
        if answer not in ('A', 'B', 'C', 'D'):
            raise QuizServiceError('invalid_option', '答案选项必须为 A、B、C 或 D', 400)
        normalized[item_id] = answer
    return normalized


def attempt_student_payload(attempt, *, created=False):
    from .quiz_snapshot import student_snapshot_questions

    now = timezone.now()
    return {
        'attempt_id': attempt.pk,
        'created': created,
        'status': attempt.status,
        'revision': attempt.answer_revision,
        'server_time': now,
        'started_at': attempt.started_at,
        'deadline_at': attempt.deadline_at,
        'remaining_seconds': _remaining_seconds(attempt, now),
        'saved_answers': attempt.answers,
        'quiz': {
            'id': attempt.session_id,
            'title': (attempt.snapshot_json or {}).get('session_title') or attempt.session.title,
            'num_questions': (attempt.snapshot_json or {}).get('question_count', 0),
            'time_limit': attempt.session.time_limit,
        },
        'questions': student_snapshot_questions(attempt.snapshot_json or {}),
    }


def _settle_locked(attempt, *, now, reason, final_answers=None, revision=None):
    if attempt.status in SETTLED_STATUSES:
        return attempt
    if attempt.status != QuizSubmission.STATUS_IN_PROGRESS:
        raise QuizServiceError('attempt_not_active', '本次作答不可提交', 409)

    past_grace = _is_past_grace(attempt, now)
    use_final = reason == 'submitted' and not past_grace and final_answers is not None
    if use_final:
        if revision != attempt.answer_revision:
            raise QuizServiceError(
                'attempt_revision_conflict', '作答版本已变化，请重新加载', 409,
                current_revision=attempt.answer_revision,
            )
        answers = _normalize_answers(attempt, final_answers)
    else:
        answers = attempt.answers

    snapshot_items = (attempt.snapshot_json or {}).get('questions', [])
    if attempt.snapshot_version != 1 or not snapshot_items:
        raise QuizServiceError('legacy_attempt_read_only', '历史作答不能重新结算', 409)

    correct_count = sum(
        1 for item in snapshot_items
        if answers.get(item['item_id']) == item['correct_option']
    )
    total_count = len(snapshot_items)
    score = round(correct_count / total_count * 100, 1) if total_count else 0.0
    status = (
        QuizSubmission.STATUS_SUBMITTED
        if reason == 'submitted' and not past_grace
        else QuizSubmission.STATUS_TIMED_OUT
    )
    attempt.answers_json = canonical_answers(answers)
    attempt.answer_revision += 1 if use_final else 0
    attempt.status = status
    attempt.score = score
    attempt.correct_count = correct_count
    attempt.total_count = total_count
    attempt.submitted_at = now
    attempt.save(update_fields=[
        'answers_json', 'answer_revision', 'status', 'score', 'correct_count',
        'total_count', 'submitted_at', 'updated_at',
    ])
    return attempt


def start_or_resume_attempt(user, session_id):
    ensure_student(user)
    User = get_user_model()
    try:
        with transaction.atomic():
            User.objects.select_for_update().get(pk=user.pk)
            try:
                session = QuizSession.objects.select_for_update().prefetch_related('units').get(
                    pk=session_id, archived_at__isnull=True,
                )
            except QuizSession.DoesNotExist as exc:
                raise QuizServiceError('quiz_not_found', '小测不存在', 404) from exc
            if session.status != QuizSession.STATUS_OPEN:
                raise QuizServiceError('quiz_not_open', '小测当前未开放', 409)

            attempt = QuizSubmission.objects.select_for_update().filter(
                user=user, session=session, current_marker=True,
            ).first()
            now = timezone.now()
            if attempt:
                if attempt.status == QuizSubmission.STATUS_IN_PROGRESS and _is_past_grace(attempt, now):
                    attempt = _settle_locked(attempt, now=now, reason='timed_out')
                if attempt.status == QuizSubmission.STATUS_IN_PROGRESS:
                    return attempt, False

                # 已结算作答保留为历史；开放期间再次进入会生成全新随机试卷。
                attempt.current_marker = None
                attempt.save(update_fields=['current_marker', 'updated_at'])

            # 已开始的本人作答可继续；生成新作答时必须重新满足最新年级和班级范围。
            ensure_student_can_access(user, session)

            try:
                snapshot = build_quiz_snapshot(session)
            except SnapshotBuildError as exc:
                raise QuizServiceError('quiz_pool_insufficient', str(exc), 409) from exc
            latest_no = QuizSubmission.objects.filter(
                user=user, session=session,
            ).aggregate(value=Max('attempt_no'))['value'] or 0
            deadline = (
                now + timedelta(minutes=session.time_limit)
                if session.time_limit else None
            )
            attempt = QuizSubmission.objects.create(
                user=user,
                session=session,
                grade=user.grade or '',
                class_num_snapshot=user.class_num or '',
                student_number_snapshot=user.student_number or '',
                status=QuizSubmission.STATUS_IN_PROGRESS,
                attempt_no=latest_no + 1,
                current_marker=True,
                snapshot_version=1,
                snapshot_json=snapshot,
                answers_json='{}',
                answer_revision=0,
                started_at=now,
                deadline_at=deadline,
                submitted_at=None,
                total_count=snapshot['question_count'],
            )
            return attempt, True
    except IntegrityError:
        attempt = QuizSubmission.objects.filter(
            user=user, session_id=session_id, current_marker=True,
        ).select_related('session').first()
        if attempt:
            return attempt, False
        raise


def get_current_attempt(user, session_id, *, settle_expired=True):
    ensure_student(user)
    with transaction.atomic():
        attempt = QuizSubmission.objects.select_for_update().select_related('session').filter(
            user=user, session_id=session_id, current_marker=True,
        ).first()
        if not attempt:
            raise QuizServiceError('attempt_not_found', '尚未开始本次小测', 404)
        now = timezone.now()
        if settle_expired and attempt.status == QuizSubmission.STATUS_IN_PROGRESS and _is_past_grace(attempt, now):
            attempt = _settle_locked(attempt, now=now, reason='timed_out')
        return attempt


def save_answers(user, session_id, attempt_id, revision, answers):
    ensure_student(user)
    with transaction.atomic():
        attempt = QuizSubmission.objects.select_for_update().select_related('session').filter(
            pk=attempt_id, user=user, session_id=session_id, current_marker=True,
        ).first()
        if not attempt:
            raise QuizServiceError('attempt_not_found', '本次作答不存在', 404)
        now = timezone.now()
        if attempt.status in SETTLED_STATUSES:
            raise QuizServiceError('attempt_completed', '本次小测已经完成', 409, result_available=True)
        if attempt.deadline_at and now > attempt.deadline_at:
            if _is_past_grace(attempt, now):
                _settle_locked(attempt, now=now, reason='timed_out')
            raise QuizServiceError(
                'attempt_deadline_reached', '作答时间已结束，不能再保存答案', 410,
                result_available=attempt.status in SETTLED_STATUSES,
            )
        if revision != attempt.answer_revision:
            raise QuizServiceError(
                'attempt_revision_conflict', '作答版本已变化，请重新加载', 409,
                current_revision=attempt.answer_revision,
            )
        normalized = _normalize_answers(attempt, answers)
        attempt.answers_json = canonical_answers(normalized)
        attempt.answer_revision += 1
        attempt.save(update_fields=['answers_json', 'answer_revision', 'updated_at'])
        return attempt


def submit_attempt(user, session_id, attempt_id, revision, answers):
    ensure_student(user)
    with transaction.atomic():
        attempt = QuizSubmission.objects.select_for_update().select_related('session').filter(
            pk=attempt_id, user=user, session_id=session_id, current_marker=True,
        ).first()
        if not attempt:
            raise QuizServiceError('attempt_not_found', '本次作答不存在', 404)
        return _settle_locked(
            attempt,
            now=timezone.now(),
            reason='submitted',
            final_answers=answers,
            revision=revision,
        )


def close_session(teacher, session):
    with transaction.atomic():
        session = QuizSession.objects.select_for_update().get(pk=session.pk)
        if session.status == QuizSession.STATUS_CLOSED:
            return session
        if session.status != QuizSession.STATUS_OPEN:
            raise QuizServiceError('invalid_quiz_transition', '只有进行中的小测可以关闭', 409)
        now = timezone.now()
        session.status = QuizSession.STATUS_CLOSED
        session.closed_at = now
        session.save(update_fields=['status', 'closed_at', 'updated_at'])
        attempts = QuizSubmission.objects.select_for_update().filter(
            session=session,
            current_marker=True,
            status=QuizSubmission.STATUS_IN_PROGRESS,
        )
        for attempt in attempts.iterator():
            _settle_locked(attempt, now=now, reason='closed')
        return session


def settle_expired_attempts(*, session_ids=None):
    cutoff = timezone.now() - timedelta(seconds=GRACE_SECONDS)
    queryset = QuizSubmission.objects.filter(
        current_marker=True,
        status=QuizSubmission.STATUS_IN_PROGRESS,
        deadline_at__isnull=False,
        deadline_at__lt=cutoff,
    )
    if session_ids is not None:
        queryset = queryset.filter(session_id__in=session_ids)
    for attempt_id in list(queryset.values_list('id', flat=True)):
        with transaction.atomic():
            attempt = QuizSubmission.objects.select_for_update().filter(pk=attempt_id).first()
            if (
                attempt
                and attempt.status == QuizSubmission.STATUS_IN_PROGRESS
                and _is_past_grace(attempt, timezone.now())
            ):
                _settle_locked(attempt, now=timezone.now(), reason='timed_out')


def reset_attempt(teacher, session, student, reason):
    reason = (reason or '').strip()
    if not reason:
        raise QuizServiceError('reset_reason_required', '请填写重置原因', 400)
    if session.status != QuizSession.STATUS_OPEN:
        raise QuizServiceError('quiz_not_open', '只有进行中的小测可以重置作答', 409)
    with transaction.atomic():
        attempt = QuizSubmission.objects.select_for_update().filter(
            user=student, session=session, current_marker=True,
        ).first()
        if not attempt:
            raise QuizServiceError('attempt_not_found', '该学生没有可重置的作答', 404)
        attempt.status = QuizSubmission.STATUS_RESET
        attempt.current_marker = None
        attempt.reset_at = timezone.now()
        attempt.reset_by = teacher
        attempt.reset_reason = reason
        attempt.save(update_fields=[
            'status', 'current_marker', 'reset_at', 'reset_by', 'reset_reason', 'updated_at',
        ])
        return attempt
