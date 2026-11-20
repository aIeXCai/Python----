from uuid import uuid4

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


GRADE_LABELS = {
    3: '三年级',
    4: '四年级',
    5: '五年级',
    6: '六年级',
    7: '七年级',
    8: '八年级',
}


class Language(models.TextChoices):
    CHINESE = 'zh', '中文'
    ENGLISH = 'en', '英文'


class TypingArticle(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    source = models.SlugField(max_length=64)
    source_id = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['source', 'source_id'], name='typing_article_source_unique',
            ),
        ]


class TypingArticleRevision(models.Model):
    class Review(models.TextChoices):
        DRAFT = 'draft', '待审'
        APPROVED = 'approved', '可发布'

    article = models.ForeignKey(
        TypingArticle, on_delete=models.PROTECT, related_name='revisions',
    )
    version = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    grade = models.PositiveSmallIntegerField(choices=tuple(GRADE_LABELS.items()))
    language = models.CharField(max_length=2, choices=Language.choices)
    difficulty = models.CharField(max_length=30)
    title = models.CharField(max_length=200)
    paragraphs = models.JSONField()
    body_digest = models.CharField(max_length=64)
    source_metadata = models.JSONField()
    pinyin = models.JSONField(null=True)
    review_status = models.CharField(max_length=8, choices=Review.choices, default=Review.DRAFT)

    @property
    def body(self):
        separator = ' ' if self.language == Language.ENGLISH else ''
        return separator.join(self.paragraphs)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['article', 'version'], name='typing_article_version_unique'),
            models.CheckConstraint(condition=models.Q(grade__in=GRADE_LABELS), name='typing_revision_grade_range'),
            models.CheckConstraint(condition=models.Q(language__in=Language.values), name='typing_revision_language'),
        ]
        indexes = [
            models.Index(fields=['grade', 'language', 'difficulty', 'review_status'], name='typing_revision_pool_idx'),
        ]


class TypingSpeedRule(models.Model):
    grade = models.PositiveSmallIntegerField(choices=tuple(GRADE_LABELS.items()))
    language = models.CharField(max_length=2, choices=Language.choices)
    difficulty = models.CharField(max_length=30)
    version = models.SlugField(max_length=50)
    target_per_minute = models.DecimalField(max_digits=7, decimal_places=2)
    is_trial = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['grade', 'language', 'difficulty', 'version', 'is_trial'],
                name='typing_speed_rule_version_unique',
            ),
            models.CheckConstraint(
                condition=models.Q(target_per_minute__gt=0, grade__in=GRADE_LABELS, language__in=Language.values),
                name='typing_speed_rule_valid',
            ),
        ]


class ArticleMode(models.TextChoices):
    FIXED = 'fixed', '固定'
    RANDOM = 'random', '随机'
    FREE = 'free', '自由'


class TypingActivity(models.Model):
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    grade = models.PositiveSmallIntegerField(choices=tuple(GRADE_LABELS.items()))
    class_num = models.CharField(max_length=20)
    title = models.CharField(max_length=100)
    languages = models.JSONField()
    published_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True)
    is_trial = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=['grade', 'class_num', 'closed_at'], name='typing_activity_class_idx'),
        ]


class TypingClassSettings(models.Model):
    grade = models.PositiveSmallIntegerField(choices=tuple(GRADE_LABELS.items()))
    class_num = models.CharField(max_length=20)
    activity = models.OneToOneField(TypingActivity, null=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['grade', 'class_num'], name='typing_settings_class_unique'),
        ]


class TypingAttempt(models.Model):
    activity = models.ForeignKey(TypingActivity, on_delete=models.PROTECT, related_name='attempts')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    active_student = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name='+',
    )
    language = models.CharField(max_length=2, choices=Language.choices)
    article_sequence = models.JSONField()
    first_article = models.ForeignKey(TypingArticleRevision, on_delete=models.PROTECT)
    started_at = models.DateTimeField()
    deadline_at = models.DateTimeField()
    checkpoint = models.JSONField(default=list)
    checkpoint_seq = models.PositiveIntegerField(default=0)
    summit_at = models.DateTimeField(null=True)
    progress = models.DecimalField(max_digits=20, decimal_places=18, default=0)
    result = models.JSONField(null=True)

    class Meta:
        indexes = [
            models.Index(fields=['activity', 'language', 'student'], name='typing_attempt_activity_idx'),
            models.Index(fields=['deadline_at'], name='typing_attempt_deadline_idx'),
        ]


class TypingPointSubmission(models.Model):
    attempt = models.OneToOneField(TypingAttempt, on_delete=models.PROTECT, related_name='point_submission')
    score = models.DecimalField(max_digits=4, decimal_places=1)
    settled_at = models.DateTimeField()
