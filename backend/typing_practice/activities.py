import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError as APIValidationError, APIException

from users.scopes import TeacherScopeError, require_teacher_grade

from .article_pool import require_article_pool
from .models import ArticleMode, GRADE_LABELS, Language, TypingActivity, TypingArticleRevision, TypingAttempt, TypingSpeedRule
from .peaks import select_peak_pair
from .scoring import DURATION_SECONDS


TRIAL_GRADES = (7, 8)
User = get_user_model()


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


def trial_speed_rules(grade, language):
    return TypingSpeedRule.objects.filter(grade=grade, language=language, is_trial=True)


@transaction.atomic
def publish_activity(teacher, data):
    grade = data['grade']
    require_class(teacher, grade, data['class_num'])
    languages = {}
    for language, peak in zip(Language.values, select_peak_pair(), strict=True):
        setup = data[language]
        difficulty = setup['difficulty']
        speed = trial_speed_rules(grade, language).filter(difficulty=difficulty).order_by('-pk').first()
        if speed is None:
            raise APIValidationError(f'请先配置{Language(language).label}该难度的试用速度线。')
        try:
            pool = require_article_pool(
                grade=grade, language=language, difficulty=difficulty,
                article_revision_id=setup.get('article_id'), pinyin=setup['pinyin'],
            )
        except ValidationError as exc:
            raise APIValidationError(exc.messages[0]) from exc
        languages[language] = {
            'mode': setup['mode'], 'difficulty': difficulty, 'pinyin': setup['pinyin'],
            'article_ids': list(pool.values_list('pk', flat=True)), 'peak': peak,
            'rule': {'version': speed.version, 'target_per_minute': str(speed.target_per_minute)},
        }
    return TypingActivity.objects.create(
        teacher=teacher, grade=grade, class_num=data['class_num'], title=data['title'], languages=languages,
    )


@transaction.atomic
def close_activity(teacher, activity_id):
    activity = teacher_activities(teacher).select_for_update().filter(pk=activity_id).first()
    if activity is None:
        raise NotFound('没有找到该场打字训练。')
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
    if active and active.deadline_at > now:
        if active.activity_id == activity.pk and active.language == language:
            return active, False
        raise AttemptConflict('已有一场训练正在计时，请先返回该场。')
    if activity.closed_at:
        raise AttemptConflict('本场已停止加入。')

    setup = activity.languages[language]
    article_ids = setup['article_ids']
    selected = data.get('article_id')
    if setup['mode'] == ArticleMode.FREE:
        if selected not in article_ids:
            raise APIValidationError('请选择本场年级、语言和难度内的文章。')
        remaining = [article_id for article_id in article_ids if article_id != selected]
        random.shuffle(remaining)
        sequence = [selected, *remaining]
    else:
        if selected is not None:
            raise APIValidationError('当前模式由教师或系统分配文章。')
        sequence = list(article_ids)
        if setup['mode'] == ArticleMode.RANDOM:
            random.shuffle(sequence)
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
