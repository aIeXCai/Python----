from django.core.exceptions import ValidationError
from django.db.models import OuterRef, Subquery

from .models import GRADE_LABELS, Language, TypingArticleRevision


def require_article_pool(*, grade, language, difficulty, article_revision_id=None):
    if type(grade) is not int or grade not in GRADE_LABELS or language not in Language.values:
        raise ValidationError('请选择有效的年级和语言。', code='invalid_article_scope')

    approved = TypingArticleRevision.objects.filter(review_status=TypingArticleRevision.Review.APPROVED)
    latest_approved = approved.filter(article_id=OuterRef('article_id')).order_by('-version').values('pk')[:1]
    pool = approved.filter(
        grade=grade, language=language, difficulty=difficulty, pk=Subquery(latest_approved),
    ).order_by('title', 'pk')
    if article_revision_id is not None:
        pool = pool.filter(pk=article_revision_id)
        if not pool.exists():
            raise ValidationError('该文章不在本场年级、语言和难度的可用题池。', code='article_out_of_scope')
    elif not pool.exists():
        raise ValidationError(f'请先补充{GRADE_LABELS[grade]}{Language(language).label}该难度的文章。', code='empty_article_pool')
    return pool
