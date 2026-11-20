from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import OuterRef, Q, Subquery

from .models import GRADE_LABELS, Language, TypingArticleRevision


FORMAL_BANK_SOURCE = 'workbuddy-typing-bank2'
ANNOTATED_SAMPLE_SOURCE = 'original-trial-v1'

def require_article_pool(*, grade, language, difficulty, article_revision_id=None, pinyin=False):
    if type(grade) is not int or grade not in GRADE_LABELS or language not in Language.values:
        raise ValidationError('请选择有效的年级和语言。', code='invalid_article_scope')

    approved = TypingArticleRevision.objects.filter(review_status=TypingArticleRevision.Review.APPROVED)
    if settings.TYPING_PRACTICE_FORMAL:
        source = Q(article__source=FORMAL_BANK_SOURCE)
        if pinyin:
            source |= Q(article__source=ANNOTATED_SAMPLE_SOURCE, pinyin__isnull=False)
        approved = approved.filter(source)
    latest_approved = approved.filter(article_id=OuterRef('article_id')).order_by('-version').values('pk')[:1]
    pool = approved.filter(
        grade=grade, language=language, difficulty=difficulty, pk=Subquery(latest_approved),
    ).order_by('title', 'pk')
    if pinyin:
        pool = pool.filter(pinyin__isnull=False)
    if article_revision_id is not None:
        pool = pool.filter(pk=article_revision_id)
        if not pool.exists():
            raise ValidationError('该文章不在本场年级、语言和难度的可用题池。', code='article_out_of_scope')
    elif not pool.exists():
        detail = '附有已核对拼音的' if pinyin else ''
        raise ValidationError(
            f'请先补充{GRADE_LABELS[grade]}{Language(language).label}该难度{detail}文章。',
            code='empty_article_pool',
        )
    return pool
