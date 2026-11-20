from uuid import uuid4

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
