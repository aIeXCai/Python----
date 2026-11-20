from decimal import Decimal, ROUND_HALF_UP, localcontext
from fractions import Fraction

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from .activities import student_activities
from .importing import is_han_character
from .models import Language, TypingArticleRevision, TypingAttempt, TypingPointSubmission
from .scoring import DURATION_SECONDS, progress_for, score_for, target_seconds


def session_articles(attempt):
    articles = TypingArticleRevision.objects.in_bulk(attempt.article_sequence)
    return [articles[pk] for pk in attempt.article_sequence]


def calculate(attempt, articles, segments):
    count = matching = typed = 0
    for index, segment in enumerate(segments):
        goal = articles[index % len(articles)].body
        text, first = segment['text'], segment['first']
        if not len(text) <= len(first) <= len(goal) or (index < len(segments) - 1 and len(text) != len(goal)):
            raise ValidationError('练习字位与原文不匹配。')
        for char, expected in zip(text, goal):
            if char == expected:
                matching += 1
                if attempt.language == Language.ENGLISH or is_han_character(expected):
                    count += 1
        typed += len(text)
    setup = attempt.activity.languages[attempt.language]
    progress = progress_for(target_seconds(
        language=attempt.language, correct_count=count, target_per_minute=setup['rule']['target_per_minute'],
    ))
    accuracy = (matching * 200 + typed) // (2 * typed) if typed else 0
    if matching < typed:
        accuracy = min(accuracy, 99)
    return count, accuracy, progress


def altitude(peak, progress):
    at_base = Decimal(str(peak['base_altitude']))
    summit = Decimal(str(peak['summit_altitude']))
    raw = int((at_base + progress * (summit - at_base)).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    peak_m = int(summit.quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return min(peak_m - 1, raw) if progress < 1 else peak_m


def summit_seconds(attempt):
    if attempt.summit_elapsed is not None:
        return attempt.summit_elapsed
    return (attempt.summit_at - attempt.started_at).total_seconds() if attempt.summit_at else None


def finish(attempt, now):
    if attempt.result is not None:
        return
    count, accuracy, progress = calculate(attempt, session_articles(attempt), attempt.checkpoint)
    score = score_for(progress)
    setup = attempt.activity.languages[attempt.language]
    attempt.result = {
        'score': str(score), 'points': str(score), 'progress': float(progress),
        'altitude': altitude(setup['peak'], attempt.progress),
        'speed': round(count / (5 if attempt.language == Language.ENGLISH else 1) / (DURATION_SECONDS / 60), 1),
        'accuracy': accuracy, 'summit': progress == 1,
        'summit_seconds': summit_seconds(attempt) if progress == 1 else None,
    }
    attempt.active_student = None
    attempt.save(update_fields=['result', 'active_student'])
    TypingPointSubmission.objects.create(attempt=attempt, score=score, settled_at=now)


@transaction.atomic
def sync_attempt(student, pk, data, *, action=None):
    attempt = TypingAttempt.objects.select_for_update().select_related('activity').filter(
        pk=pk, student=student, activity__in=student_activities(student),
    ).first()
    if attempt is None:
        raise NotFound('没有找到该次练习。')
    now = timezone.now()
    if attempt.result is not None:
        return attempt
    if attempt.paused_at:
        if action == 'resume':
            attempt.deadline_at += now - attempt.paused_at
            attempt.paused_at = None
            attempt.save(update_fields=['deadline_at', 'paused_at'])
        return attempt
    if data is not None and now <= attempt.deadline_at and data['seq'] > attempt.checkpoint_seq:
        segments = data['segments']
        frozen = attempt.checkpoint[:-1]
        if segments[:len(frozen)] != frozen:
            raise ValidationError('已经完成的篇目不能改动。')
        for old, new in zip(attempt.checkpoint, segments):
            if not new['first'].startswith(old['first']):
                raise ValidationError('首次输入记录不能被修改。')
        if len(segments) < len(attempt.checkpoint):
            raise ValidationError('练习篇目不能回退。')
        _, _, progress = calculate(attempt, session_articles(attempt), segments)
        with localcontext() as ctx:
            ctx.prec = 30
            attempt.progress = (Decimal(progress.numerator) / progress.denominator).quantize(Decimal('1e-18'))
        if progress < 1:
            attempt.progress = min(attempt.progress, Decimal('0.999999999999999999'))
        elif attempt.summit_at is None:
            attempt.summit_at = now
            attempt.summit_elapsed = DURATION_SECONDS - (attempt.deadline_at - now).total_seconds()
        attempt.checkpoint = segments
        attempt.checkpoint_seq = data['seq']
        attempt.save(update_fields=['checkpoint', 'checkpoint_seq', 'progress', 'summit_at', 'summit_elapsed'])
    if now >= attempt.deadline_at:
        finish(attempt, now)
    elif action == 'pause':
        attempt.paused_at = now
        attempt.save(update_fields=['paused_at'])
    return attempt


def leaderboard(student, activity, language):
    entries = {}
    records = TypingAttempt.objects.filter(
        activity=activity, language=language, student__grade=student.grade,
        student__class_num=activity.class_num,
    ).select_related('student').order_by('-progress', '-started_at')
    peak = activity.languages[language]['peak']
    for row in records:
        if row.student_id not in entries:
            entries[row.student_id] = row
    output = []
    previous = None
    for index, row in enumerate(entries.values(), 1):
        if row.progress != previous:
            rank = index
        previous = row.progress
        output.append({
            'id': row.student_id, 'label': f'{row.student.student_number} 号', 'self': row.student_id == student.pk,
            'progress': float(row.progress), 'altitude': altitude(peak, row.progress), 'rank': rank,
        })
    return output
