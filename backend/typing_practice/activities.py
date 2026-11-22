import random
from datetime import datetime, time, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError as APIValidationError, APIException

from users.scopes import TeacherScopeError, require_teacher_grade

from .article_pool import require_article_pool
from .importing import is_han_character
from .models import (
    ArticleMode, GRADE_LABELS, Language, TypingActivity, TypingArticleRevision,
    TypingAttempt, TypingClassSettings, TypingPracticeSettings, TypingSpeedRule,
)
from .peaks import select_peak_pair
from .scoring import DURATION_SECONDS


TRIAL_GRADES = (7, 8)
User = get_user_model()
DIFFICULTY_ORDER = ('基础', '进阶', '挑战')


class AttemptConflict(APIException):
    status_code = 409
    default_code = 'typing_attempt_conflict'


def managed_grades(teacher):
    try:
        label = require_teacher_grade(teacher)
    except TeacherScopeError as exc:
        raise PermissionDenied(exc.message) from exc
    return [grade for grade in TRIAL_GRADES if label is None or GRADE_LABELS[grade] == label]


def teacher_activities(teacher):
    return TypingActivity.objects.filter(grade__in=managed_grades(teacher))


def require_class(teacher, grade, class_num):
    if grade not in managed_grades(teacher):
        raise PermissionDenied('不能访问管理范围外的年级。')
    if not User.objects.filter(
        role='student', is_active=True, grade=GRADE_LABELS[grade], class_num=class_num,
    ).exists():
        raise APIValidationError('目标班级暂无可参与的学生。')


def student_activities(student):
    grades = [grade for grade in TRIAL_GRADES if GRADE_LABELS[grade] == student.grade]
    return TypingActivity.objects.filter(grade__in=grades, class_num=student.class_num)


def speed_rules(grade, language):
    return TypingSpeedRule.objects.filter(grade=grade, language=language, is_trial=not settings.TYPING_PRACTICE_FORMAL)


def ordered_difficulties(grade, language):
    available = set(speed_rules(grade, language).values_list('difficulty', flat=True))
    return [difficulty for difficulty in DIFFICULTY_ORDER if difficulty in available] + sorted(
        available.difference(DIFFICULTY_ORDER),
    )


def chinese_random_articles(articles):
    prose = list(articles.filter(
        Q(source_metadata__genre__isnull=True) | ~Q(source_metadata__genre='诗歌'),
    ))
    longer = [
        article for article in prose
        if sum(is_han_character(char) for char in article.body) >= 180
    ]
    return longer or prose


def language_snapshot(grade, language, setup, peak):
    difficulty = setup['difficulty']
    speed = speed_rules(grade, language).filter(difficulty=difficulty).order_by('-pk').first()
    if speed is None:
        raise APIValidationError(f'请先配置{Language(language).label}该难度的速度线。')
    try:
        pool = require_article_pool(
            grade=grade, language=language, difficulty=difficulty,
            article_revision_id=setup.get('article_id'), pinyin=setup['pinyin'],
        )
    except ValidationError as exc:
        raise APIValidationError(exc.messages[0], code=exc.code) from exc
    chinese_random = language == Language.CHINESE and setup['mode'] == ArticleMode.RANDOM
    if chinese_random:
        article_ids = [article.pk for article in chinese_random_articles(pool)]
        if not article_ids:
            raise APIValidationError('该难度暂无可随机抽取的中文文章。', code='empty_article_pool')
    else:
        article_ids = list(pool.values_list('pk', flat=True))
    return {
        'mode': setup['mode'], 'difficulty': difficulty, 'pinyin': setup['pinyin'],
        'article_ids': article_ids, 'peak': peak,
        'rule': {'version': speed.version, 'target_per_minute': str(speed.target_per_minute)},
        **({'long_prose_pool': True} if chinese_random else {}),
    }


def lock_class_settings(grade, class_num):
    class_settings, _ = TypingClassSettings.objects.get_or_create(grade=grade, class_num=class_num)
    return TypingClassSettings.objects.select_for_update().get(pk=class_settings.pk)


def next_rotation_at(now):
    midnight = datetime.combine(timezone.localdate(now) + timedelta(days=1), time.min)
    return timezone.make_aware(midnight, timezone.get_current_timezone())


def practice_settings():
    return TypingPracticeSettings.objects.filter(is_trial=not settings.TYPING_PRACTICE_FORMAL).first()


def practice_revision(config):
    return config.revision if config else int(settings.TYPING_PRACTICE_FORMAL)


def current_activity(grade, class_num):
    current = TypingClassSettings.objects.select_related('activity').filter(
        grade=grade, class_num=class_num, activity__isnull=False, activity__closed_at__isnull=True,
    ).first()
    revision = practice_revision(practice_settings())
    if (current and current.activity.is_trial != settings.TYPING_PRACTICE_FORMAL
            and current.activity.settings_revision == revision
            and timezone.localdate(current.activity.published_at) == timezone.localdate()):
        return current.activity
    return ensure_current_activity(grade, class_num)


def latest_activity(grade, class_num):
    return TypingActivity.objects.filter(
        grade=grade, class_num=class_num, closed_at__isnull=True,
        is_trial=not settings.TYPING_PRACTICE_FORMAL,
    ).order_by('-published_at', '-pk').first()


def activate_class_activity(class_settings, activity, now):
    if class_settings.activity_id == activity.pk:
        return
    TypingActivity.objects.filter(
        grade=activity.grade, class_num=activity.class_num, closed_at__isnull=True,
    ).exclude(pk=activity.pk).update(closed_at=now)
    class_settings.activity = activity
    class_settings.save(update_fields=['activity'])


def daily_peaks(previous, now):
    if previous is None:
        return select_peak_pair()
    if timezone.localdate(previous.published_at) == timezone.localdate(now):
        return [previous.languages[language]['peak'] for language in Language.values]
    previous_ids = [previous.languages[language]['peak']['id'] for language in Language.values]
    return select_peak_pair(exclude=previous_ids)


@transaction.atomic
def ensure_current_activity(grade, class_num):
    class_settings = lock_class_settings(grade, class_num)
    activity = latest_activity(grade, class_num)
    now = timezone.now()
    config = practice_settings()
    revision = practice_revision(config)
    same_settings = activity is not None and activity.settings_revision == revision
    if same_settings and timezone.localdate(activity.published_at) == timezone.localdate(now):
        activate_class_activity(class_settings, activity, now)
        return activity

    pools = activity.languages if same_settings else config.pools.get(str(grade)) if config else None
    languages = {}
    for language, peak in zip(Language.values, daily_peaks(activity or class_settings.activity, now), strict=True):
        if pools is not None:
            languages[language] = {**pools[language], 'peak': peak}
            continue
        for difficulty in ordered_difficulties(grade, language):
            try:
                languages[language] = language_snapshot(grade, language, {
                    'mode': ArticleMode.RANDOM, 'difficulty': difficulty, 'pinyin': False,
                }, peak)
            except APIValidationError as exc:
                if exc.get_codes() != ['empty_article_pool']:
                    raise
            else:
                break
        if language not in languages:
            return None
    activity = TypingActivity.objects.create(
        grade=grade, class_num=class_num, title=activity.title if same_settings else '打字训练',
        teacher_id=activity.teacher_id if same_settings else None, languages=languages,
        is_trial=not settings.TYPING_PRACTICE_FORMAL, settings_revision=revision,
    )

    activate_class_activity(class_settings, activity, now)
    return activity


@transaction.atomic
def publish_activity(teacher, data):
    grade, class_num = data['grade'], data['class_num']
    require_class(teacher, grade, class_num)
    if practice_revision(practice_settings()):
        raise PermissionDenied('请在教师首页修改统一训练设置。')
    class_settings = lock_class_settings(grade, class_num)
    now = timezone.now()
    previous = latest_activity(grade, class_num) or class_settings.activity
    languages = {
        language: language_snapshot(grade, language, data[language], peak)
        for language, peak in zip(Language.values, daily_peaks(previous, now), strict=True)
    }
    activity = TypingActivity.objects.create(
        teacher=teacher, grade=grade, class_num=class_num, title=data['title'], languages=languages,
        is_trial=not settings.TYPING_PRACTICE_FORMAL,
    )
    activate_class_activity(class_settings, activity, now)
    return activity


@transaction.atomic
def close_activity(teacher, activity_id):
    activity = teacher_activities(teacher).filter(pk=activity_id).first()
    if activity is None:
        raise NotFound('没有找到该场打字训练。')
    if practice_revision(practice_settings()):
        raise PermissionDenied('打字训练统一开放。')
    lock_class_settings(activity.grade, activity.class_num)
    activity.refresh_from_db(fields=['closed_at'])
    if activity.closed_at is None:
        activity.closed_at = timezone.now()
        activity.save(update_fields=['closed_at'])
    return activity


@transaction.atomic
def start_attempt(student, data):
    student = User.objects.select_for_update().get(pk=student.pk)
    activity = student_activities(student).select_for_update().filter(pk=data['activity_id']).first()
    if activity is None:
        raise NotFound('没有找到该场打字训练。')

    now = timezone.now()
    active = TypingAttempt.objects.filter(active_student=student).first()
    language = data['language']
    if active and (active.paused_at or active.deadline_at > now):
        if active.activity_id == activity.pk and active.language == language:
            return active, False
        raise AttemptConflict('已有一场训练正在计时，请先返回该场。')
    if (activity.closed_at or activity.is_trial == settings.TYPING_PRACTICE_FORMAL
            or activity.settings_revision != practice_revision(practice_settings())
            or timezone.localdate(activity.published_at) != timezone.localdate(now)):
        raise AttemptConflict('训练已更新，请重新开始。')

    setup = activity.languages[language]
    article_ids = setup['article_ids']
    selected = data.get('article_id')
    if setup['mode'] == ArticleMode.FREE:
        if selected not in article_ids:
            raise APIValidationError('请选择本场年级、语言和难度内的文章。')
        sequence = [selected]
    else:
        if selected is not None:
            raise APIValidationError('当前模式由教师或系统分配文章。')
        if language == Language.CHINESE and setup['mode'] == ArticleMode.RANDOM and not setup.get('long_prose_pool'):
            candidates = TypingArticleRevision.objects.filter(
                pk__in=article_ids, grade=activity.grade, language=language,
            )
            article_ids = [article.pk for article in chinese_random_articles(candidates)]
        if not article_ids:
            raise AttemptConflict('本场暂无可用文章。')
        sequence = [random.choice(article_ids)] if setup['mode'] == ArticleMode.RANDOM else article_ids[:1]
    if not sequence:
        raise AttemptConflict('本场暂无可用文章。')

    first = TypingArticleRevision.objects.filter(pk=sequence[0], grade=activity.grade, language=language).first()
    if first is None:
        raise AttemptConflict('本场文章不可用，请联系教师。')
    # Expired attempts remain available to the later settlement service.
    if active:
        active.active_student = None
        active.save(update_fields=['active_student'])
    attempt = TypingAttempt.objects.create(
        activity=activity, student=student, active_student=student, language=language,
        first_article=first, article_sequence=sequence, started_at=now,
        deadline_at=now + timedelta(seconds=DURATION_SECONDS),
    )
    return attempt, True
