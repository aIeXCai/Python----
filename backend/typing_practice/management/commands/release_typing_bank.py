from collections import Counter
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from typing_practice.activities import TRIAL_GRADES
from typing_practice.article_pool import FORMAL_BANK_SOURCE
from typing_practice.importing import read_bank
from typing_practice.models import Language, TypingArticleRevision, TypingSpeedRule
from .seed_typing_trial import TRIAL_SPEEDS, seed_sample_articles


class Command(BaseCommand):
    help = '安装已核对的正式打字题库，保留待核对材料与历史文章版本。'

    def add_arguments(self, parser):
        parser.add_argument('jsonl', type=Path)

    @transaction.atomic
    def handle(self, *, jsonl, **options):
        try:
            entries, errors = read_bank(jsonl)
        except (OSError, UnicodeError) as exc:
            raise CommandError(f'无法读取 UTF-8 JSONL：{exc}') from exc
        if errors:
            raise CommandError('\n'.join(errors))
        published = {
            source_id: fields for source_id, fields in entries
            if fields['source_metadata']['edition_check_status'] == '已核对'
        }
        counts = Counter((fields['grade'], fields['language']) for fields in published.values())
        for grade in TRIAL_GRADES:
            for language in Language.values:
                if not counts[grade, language]:
                    raise CommandError(f'正式题库缺少 {grade} 年级 {language} 的已核对文章。')

        for grade, speeds_by_language in TRIAL_SPEEDS.items():
            for language, targets in speeds_by_language.items():
                for difficulty, target in zip(('基础', '进阶', '挑战'), targets, strict=True):
                    speed = TypingSpeedRule.objects.filter(
                        grade=grade, language=language, difficulty=difficulty, is_trial=True,
                    ).order_by('-pk').first()
                    TypingSpeedRule.objects.get_or_create(
                        grade=grade, language=language, difficulty=difficulty, is_trial=False, version='formal-v1',
                        defaults={'target_per_minute': speed.target_per_minute if speed else target},
                    )

        seed_sample_articles(annotated_only=True)
        call_command('import_typing_bank', jsonl, source=FORMAL_BANK_SOURCE, accept_revisions=True)
        previous = TypingArticleRevision.objects.filter(article__source=FORMAL_BANK_SOURCE).select_related('article')
        ids = set()
        pending = dict(published)
        for revision in previous.order_by('-version'):
            source_id = revision.article.source_id
            fields = pending.get(source_id)
            if fields and all(getattr(revision, field) == value for field, value in fields.items()):
                ids.add(revision.pk)
                del pending[source_id]
        if pending:
            raise CommandError(f'{len(pending)} 篇已核对文章找不到对应的导入版本。')
        previous.filter(review_status=TypingArticleRevision.Review.APPROVED).exclude(pk__in=ids).update(
            review_status=TypingArticleRevision.Review.DRAFT,
        )
        previous.filter(pk__in=ids).update(review_status=TypingArticleRevision.Review.APPROVED)
        self.stdout.write(self.style.SUCCESS(f'正式可选 {len(ids)} 篇，待审 {len(entries) - len(ids)} 篇。'))
