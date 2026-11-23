from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from django.core.validators import validate_slug
from django.db import transaction

from typing_practice.importing import is_han_character, read_bank
from typing_practice.models import Language, TypingArticle, TypingArticleRevision


# 编制规格的五分钟篇幅参考值（汉字数、英文字符数），仅供审阅报告。
# 2026-11 起线上题库换成新闻体，七、八年级给足冗余：满分只需 110–150 汉字 / 450–500 字符，
# 文章写到 300+ 汉字 / 1200+ 字符，手快的学生五分钟也打不完。
REFERENCE_LENGTHS = {3: (75, 250), 4: (85, 290), 5: (95, 330),
                     6: (110, 380), 7: (300, 1200), 8: (340, 1300)}


class Command(BaseCommand):
    help = '校验并导入分年级打字题库，导入文章版本默认为待审。'

    def add_arguments(self, parser):
        parser.add_argument('jsonl', type=Path)
        parser.add_argument('--source', default='workbuddy-typing-bank2',
                            help='稳定的来源名。分库和全量使用同一个来源名。')
        parser.add_argument('--dry-run', action='store_true', help='仅报告校验、复核项及拟导入数量')
        parser.add_argument('--accept-revisions', action='store_true',
                            help='确认来源 ID 仍指同一篇文章，允许变更内容进入新待审版本')

    def handle(self, *, jsonl, source, dry_run, accept_revisions, **options):
        try:
            validate_slug(source)
            if len(source) > 64:
                raise ValidationError('来源名过长')
        except ValidationError as exc:
            raise CommandError('--source 必须为不超过 64 字符的 slug') from exc
        try:
            entries, errors = read_bank(jsonl)
        except (OSError, UnicodeError) as exc:
            raise CommandError(f'无法读取 UTF-8 JSONL：{exc}') from exc

        for error in errors:
            self.stderr.write(error)
        self.stdout.write(f'通过结构校验 {len(entries)} 条，错误 {len(errors)} 条')
        if errors or not entries:
            raise CommandError('题库为空或存在校验错误，数据库未写入')

        with transaction.atomic():
            counts = self.import_entries(source, entries, accept_revisions, dry_run=dry_run)
        self.report_review_items(entries)

        self.stdout.write(
            f'新增文章 {counts["new"]}，重复跳过 {counts["unchanged"]}，'
            f'新增待审版本 {counts["versioned"]}，来源 ID 内容变更待核对 {counts["conflicts"]}'
        )
        if dry_run:
            self.stdout.write('干运行结束，数据库未写入。可导入条目仍需审阅。')

    def report_review_items(self, entries):
        counts = Counter()
        for _, fields in entries:
            metadata = fields['source_metadata']
            counts['edition'] += metadata['edition_check_status'] != '已核对'
            counts['public_domain'] += metadata['material_type'] == '公版原作'
            han_length, english_length = REFERENCE_LENGTHS[fields['grade']]
            if fields['language'] == Language.CHINESE:
                length = sum(is_han_character(char) for part in fields['paragraphs'] for char in part)
                counts['short'] += length < han_length
            else:
                counts['short'] += len(' '.join(fields['paragraphs'])) < english_length
        self.stdout.write(
            f'分册待核对 {counts["edition"]}，公版来源待复核 {counts["public_domain"]}，'
            f'按编制规格预计不足五分钟 {counts["short"]}'
        )

    def import_entries(self, source, entries, accept_revisions, *, dry_run):
        counts = Counter()
        for source_id, fields in entries:
            articles = TypingArticle.objects.filter(source=source, source_id=source_id)
            if dry_run:
                article = articles.first()
            else:
                article, _ = articles.get_or_create(source=source, source_id=source_id)
                article = articles.select_for_update().get()
            revisions = list(article.revisions.order_by('-version')) if article else []
            if not revisions:
                counts['new'] += 1
                if not dry_run:
                    TypingArticleRevision.objects.create(article=article, version=1, **fields)
                continue

            latest = revisions[0]
            if any(all(getattr(row, key) == value for key, value in fields.items()) for row in revisions):
                counts['unchanged'] += 1
            elif accept_revisions:
                counts['versioned'] += 1
                if not dry_run:
                    TypingArticleRevision.objects.create(article=article, version=latest.version + 1, **fields)
            else:
                counts['conflicts'] += 1
                self.stderr.write(f'{source_id} 与最近版本 v{latest.version} 不一致，待人工核对')
        return counts
