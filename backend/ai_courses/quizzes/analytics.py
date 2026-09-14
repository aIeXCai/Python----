"""Teacher analytics for immutable AI quiz attempts.

All question labels, choices and points come from attempt snapshots.  The
responses intentionally omit student source code and hidden test snapshots.
"""

from collections import Counter, defaultdict
from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone

from users.models import CustomUser

from ..models import (
    AUDIENCE_ALL_SCHOOL,
    AUDIENCE_CLASS,
    AUDIENCE_GRADE_ALL,
    AIQuizAttempt,
    AIQuizSession,
    Submission,
)
from .services import AIQuizServiceError, scoped_quizzes
from .settlement_services import finalize_attempt, request_system_settlement


FINAL_STATUSES = {
    AIQuizAttempt.STATUS_SUBMITTED,
    AIQuizAttempt.STATUS_TIMED_OUT,
    AIQuizAttempt.STATUS_CLOSED,
    AIQuizAttempt.STATUS_SUPERSEDED,
}


def _session(actor, session_id):
    try:
        return scoped_quizzes(actor, include_archived=True).get(pk=session_id)
    except AIQuizSession.DoesNotExist as exc:
        raise AIQuizServiceError(
            '小测不存在', code='quiz_not_found', status_code=404,
        ) from exc


def _participants(session):
    rules = list(session.audience_rules.filter(is_active=True))
    if not rules:
        return CustomUser.objects.none()
    base = CustomUser.objects.filter(role='student', is_active=True)
    if any(rule.scope_type == AUDIENCE_ALL_SCHOOL for rule in rules):
        return base.order_by('grade', 'class_num', 'student_number', 'id')
    condition = Q(pk__in=[])
    for rule in rules:
        if rule.scope_type == AUDIENCE_GRADE_ALL:
            condition |= Q(grade=rule.grade)
        elif rule.scope_type == AUDIENCE_CLASS:
            condition |= Q(grade=rule.grade, class_num=rule.class_num)
    return base.filter(condition).order_by(
        'grade', 'class_num', 'student_number', 'id',
    ).distinct()


def _snapshot_items(attempt, item_type):
    return [
        item for item in (attempt.snapshot_json or {}).get('items', [])
        if item.get('type') == item_type
    ]


def _latest_final_by_user(attempts):
    latest = {}
    for attempt in sorted(attempts, key=lambda value: (value.user_id, -value.attempt_no)):
        if attempt.user_id not in latest and attempt.status in FINAL_STATUSES and attempt.total_score is not None:
            latest[attempt.user_id] = attempt
    return latest


def _current_by_user(attempts):
    return {attempt.user_id: attempt for attempt in attempts if attempt.current_marker is True}


def _best_by_user(attempts):
    values = defaultdict(list)
    for attempt in attempts:
        if attempt.total_score is not None and attempt.status in FINAL_STATUSES:
            values[attempt.user_id].append(attempt.total_score)
    return {user_id: max(scores) for user_id, scores in values.items()}


def _format_score(value):
    return format(value, '.1f') if value is not None else None


def _page(values, page, page_size):
    try:
        page = max(1, int(page or 1))
        page_size = min(100, max(1, int(page_size or 20)))
    except (TypeError, ValueError) as exc:
        raise AIQuizServiceError('分页参数无效', code='invalid_pagination') from exc
    paginator = Paginator(values, page_size)
    page_obj = paginator.get_page(page)
    return page_obj, {
        'page': page_obj.number,
        'page_size': page_size,
        'total': paginator.count,
        'pages': paginator.num_pages,
    }


def _attempts(session, user_ids=None):
    queryset = AIQuizAttempt.objects.filter(session=session).select_related('user')
    if user_ids is not None:
        queryset = queryset.filter(user_id__in=user_ids)
    return list(queryset.order_by('user_id', '-attempt_no'))


def _programming_scores(attempt_ids):
    submissions = Submission.objects.filter(
        quiz_attempt_id__in=attempt_ids,
        counts_for_quiz=True,
        score__isnull=False,
    ).values('quiz_attempt_id', 'quiz_item_id', 'score')
    scores = defaultdict(list)
    for submission in submissions:
        scores[(submission['quiz_attempt_id'], submission['quiz_item_id'])].append(submission['score'])
    return scores


def quiz_overview(actor, session_id):
    session = _session(actor, session_id)
    now = timezone.now()
    for attempt_id in AIQuizAttempt.objects.filter(
        session=session, status=AIQuizAttempt.STATUS_IN_PROGRESS,
        current_marker=True, deadline_at__isnull=False, deadline_at__lte=now,
    ).values_list('pk', flat=True):
        request_system_settlement(attempt_id, 'timed_out')
    for attempt_id in AIQuizAttempt.objects.filter(
        session=session, status=AIQuizAttempt.STATUS_SETTLING,
    ).values_list('pk', flat=True):
        finalize_attempt(attempt_id)
    participants = list(_participants(session).values_list('id', flat=True))
    attempts = _attempts(session)
    participant_set = set(participants)
    scoped_attempts = [attempt for attempt in attempts if attempt.user_id in participant_set]
    current = _current_by_user(scoped_attempts)
    latest = _latest_final_by_user(scoped_attempts)
    scores = [attempt.total_score for attempt in latest.values()]
    statuses = Counter(attempt.status for attempt in current.values())
    started = {attempt.user_id for attempt in scoped_attempts}
    choice_rates = [
        Decimal(attempt.correct_count) * Decimal('100') / Decimal(attempt.choice_count)
        for attempt in latest.values() if attempt.choice_count
    ]
    return {
        'quiz': {
            'id': session.pk, 'title': session.title, 'status': session.status,
            'content_grade': session.content_grade,
        },
        'participation': {
            'expected': len(participants),
            'started': len(started),
            'not_started': max(0, len(participants) - len(started)),
            'in_progress': statuses[AIQuizAttempt.STATUS_IN_PROGRESS],
            'settling': statuses[AIQuizAttempt.STATUS_SETTLING],
            'submitted': len(latest),
            'timed_out': statuses[AIQuizAttempt.STATUS_TIMED_OUT],
        },
        'scores': {
            'count': len(scores),
            'average': _format_score(sum(scores, Decimal('0')) / len(scores)) if scores else None,
            'highest': _format_score(max(scores)) if scores else None,
            'lowest': _format_score(min(scores)) if scores else None,
            'pass_rate': _format_score(
                Decimal(sum(1 for score in scores if score >= 60)) * Decimal('100') / len(scores)
            ) if scores else None,
            'choice_average_rate': _format_score(
                sum(choice_rates, Decimal('0')) / len(choice_rates)
            ) if choice_rates else None,
        },
    }


def _natural_identifier(value):
    text = str(value or '').strip()
    try:
        return 0, int(text), text
    except ValueError:
        return 1, 0, text.casefold()


def quiz_students(
    actor, session_id, *, page=1, page_size=20, grade='', class_num='',
    status='', query='',
):
    session = _session(actor, session_id)
    students = list(_participants(session))
    attempts = _attempts(session, [student.pk for student in students])
    current = _current_by_user(attempts)
    latest = _latest_final_by_user(attempts)
    best = _best_by_user(attempts)
    attempt_counts = Counter(attempt.user_id for attempt in attempts)
    programming = _programming_scores([attempt.pk for attempt in latest.values()])
    needle = (query or '').strip().lower()
    rows = []
    for student in students:
        current_attempt = current.get(student.pk)
        final_attempt = latest.get(student.pk)
        current_status = current_attempt.status if current_attempt else ('completed' if final_attempt else 'not_started')
        if grade and str(student.grade or '') != str(grade):
            continue
        if class_num and str(student.class_num or '') != str(class_num):
            continue
        if status and current_status != status:
            continue
        haystack = ' '.join(filter(None, [student.username, student.display_name, student.student_number])).lower()
        if needle and needle not in haystack:
            continue
        item_scores = []
        if final_attempt:
            for item in _snapshot_items(final_attempt, 'programming'):
                values = programming.get((final_attempt.pk, item.get('item_id')), [])
                item_scores.append({
                    'item_id': item.get('item_id'),
                    'title': item.get('title', ''),
                    'best_score': max(values) if values else None,
                })
        rows.append({
            'student_id': student.pk,
            'username': student.username,
            'display_name': student.display_name or student.username,
            'grade': student.grade or '',
            'class_num': student.class_num or '',
            'student_number': student.student_number or '',
            'status': current_status,
            'current_attempt_id': current_attempt.pk if current_attempt else None,
            'latest_attempt_id': final_attempt.pk if final_attempt else None,
            'latest_total_score': _format_score(final_attempt.total_score) if final_attempt else None,
            'best_total_score': _format_score(best.get(student.pk)),
            'choice_score': _format_score(final_attempt.choice_score) if final_attempt else None,
            'programming_score': _format_score(final_attempt.programming_score) if final_attempt else None,
            'programming_items': item_scores,
            'attempt_count': attempt_counts[student.pk],
            'settled_at': final_attempt.settled_at if final_attempt else None,
            'can_reset': bool(current_attempt and session.status == AIQuizSession.STATUS_OPEN),
        })
    rows.sort(key=lambda row: (
        _natural_identifier(row['student_number']),
        row['grade'],
        _natural_identifier(row['class_num']),
        row['display_name'],
        row['student_id'],
    ))
    lamp_students = [{
        'student_id': row['student_id'],
        'display_name': row['display_name'],
        'grade': row['grade'],
        'class_num': row['class_num'],
        'student_number': row['student_number'],
        'best_total_score': row['best_total_score'],
    } for row in rows]
    page_obj, pagination = _page(rows, page, page_size)
    return {
        'results': list(page_obj.object_list),
        'lamp_students': lamp_students,
        'pagination': pagination,
    }


def student_attempts(actor, session_id, student_id, *, page=1, page_size=10):
    session = _session(actor, session_id)
    if not _participants(session).filter(pk=student_id).exists():
        raise AIQuizServiceError('学生不在小测范围内', code='student_not_found', status_code=404)
    attempts = list(AIQuizAttempt.objects.filter(
        session=session, user_id=student_id,
    ).order_by('-attempt_no'))
    page_obj, pagination = _page(attempts, page, page_size)
    selected = list(page_obj.object_list)
    programming = _programming_scores([attempt.pk for attempt in selected])
    issue_items = set(Submission.objects.filter(
        quiz_attempt_id__in=[attempt.pk for attempt in selected],
        counts_for_quiz=True, score__isnull=True,
        execution_task__status__in=('system_error', 'cancelled'),
    ).values_list('quiz_attempt_id', 'quiz_item_id'))
    results = []
    for attempt in selected:
        items = []
        for item in _snapshot_items(attempt, 'programming'):
            values = programming.get((attempt.pk, item.get('item_id')), [])
            items.append({
                'item_id': item.get('item_id'), 'title': item.get('title', ''),
                'best_score': max(values) if values else None,
                'submission_count': len(values),
                'status': 'system_issue' if (attempt.pk, item.get('item_id')) in issue_items else ('scored' if values else 'not_submitted'),
            })
        results.append({
            'attempt_id': attempt.pk, 'attempt_no': attempt.attempt_no,
            'status': attempt.status, 'final_reason': attempt.final_reason,
            'total_score': _format_score(attempt.total_score),
            'choice_score': _format_score(attempt.choice_score),
            'programming_score': _format_score(attempt.programming_score),
            'correct_count': attempt.correct_count, 'choice_count': attempt.choice_count,
            'grading_issue_count': attempt.grading_issue_count,
            'started_at': attempt.started_at, 'settled_at': attempt.settled_at,
            'reset_at': attempt.reset_at, 'reset_reason': attempt.reset_reason,
            'result_revision': attempt.result_revision,
            'programming_items': items,
        })
    return {'results': results, 'pagination': pagination}


def quiz_item_analysis(actor, session_id):
    session = _session(actor, session_id)
    participant_ids = set(_participants(session).values_list('id', flat=True))
    attempts = [attempt for attempt in _attempts(session) if attempt.user_id in participant_ids]
    latest = list(_latest_final_by_user(attempts).values())
    choice_groups = {}
    for attempt in latest:
        answers = attempt.answers_json or {}
        for item in _snapshot_items(attempt, 'choice'):
            key = f"{item.get('source_question_id')}:{item.get('source_version')}"
            group = choice_groups.setdefault(key, {
                'source_question_id': item.get('source_question_id'),
                'source_version': item.get('source_version'),
                'text': item.get('text', ''), 'difficulty': item.get('difficulty', ''),
                'options': {}, 'correct_option': None,
                'answered': 0, 'correct': 0, 'unanswered': 0,
                'option_counts': {letter: 0 for letter in 'ABCD'},
            })
            mapping = item.get('source_option_by_display') or {}
            displayed = item.get('options') or {}
            for display, source in mapping.items():
                if source in 'ABCD':
                    group['options'][source] = displayed.get(display, '')
            correct_source = mapping.get(item.get('correct_display_option'))
            if correct_source in 'ABCD':
                group['correct_option'] = correct_source
            selected_display = answers.get(item.get('item_id'))
            if not selected_display:
                group['unanswered'] += 1
            else:
                group['answered'] += 1
                selected_source = mapping.get(selected_display)
                if selected_source in 'ABCD':
                    group['option_counts'][selected_source] += 1
                if selected_display == item.get('correct_display_option'):
                    group['correct'] += 1
    choices = []
    for group in choice_groups.values():
        total = group['answered'] + group['unanswered']
        group['response_count'] = total
        group['correct_rate'] = round(group['correct'] * 100 / total, 1) if total else None
        choices.append(group)

    submissions = Submission.objects.filter(
        quiz_attempt_id__in=[attempt.pk for attempt in latest], counts_for_quiz=True,
    ).select_related('execution_task')
    by_item = defaultdict(list)
    for submission in submissions:
        by_item[submission.quiz_item_id].append(submission)
    programming = []
    blueprint_items = (session.blueprint_json or {}).get('programming_items') or []
    for item in sorted(blueprint_items, key=lambda value: value.get('position', 0)):
        item_submissions = by_item.get(item.get('item_id'), [])
        by_attempt = defaultdict(list)
        terminal = Counter()
        for submission in item_submissions:
            by_attempt[submission.quiz_attempt_id].append(submission)
            status = getattr(submission.execution_task, 'status', '') or submission.status or 'unknown'
            terminal[status] += 1
        best_scores = [
            max(value.score for value in values if value.score is not None)
            for values in by_attempt.values() if any(value.score is not None for value in values)
        ]
        programming.append({
            'item_id': item.get('item_id'), 'title': item.get('title', ''),
            'points': item.get('points', '0.0'),
            'student_count': len(latest),
            'submitted_count': len(by_attempt),
            'passed_count': sum(1 for score in best_scores if score >= 100),
            'average_best_score': round(sum(best_scores) / len(best_scores), 1) if best_scores else None,
            'pass_rate': round(sum(1 for score in best_scores if score >= 100) * 100 / len(latest), 1) if latest else None,
            'average_submission_count': round(len(item_submissions) / len(by_attempt), 1) if by_attempt else 0,
            'terminal_statuses': dict(terminal.most_common()),
        })
    return {'choice_items': choices, 'programming_items': programming, 'attempt_count': len(latest)}
