import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from typing_practice.importing import is_han_character
from typing_practice.models import Language, TypingArticle, TypingArticleRevision, TypingSpeedRule


SAMPLE_PATH = Path(__file__).resolve().parents[2] / 'samples' / 'original-v1.json'
SAMPLE_SOURCE = 'original-trial-v1'
TRIAL_SPEEDS = {
    7: {Language.CHINESE: (26, 24, 22), Language.ENGLISH: (18, 16, 14)},
    8: {Language.CHINESE: (30, 28, 26), Language.ENGLISH: (20, 18, 16)},
}


class Command(BaseCommand):
    help = '在本地试用库安装原创样文和用于验算的临时速度线。'

    @transaction.atomic
    def handle(self, **options):
        if settings.ENVIRONMENT not in {'development', 'test'}:
            raise CommandError('原创试用样文只在开发和测试环境安装。')
        samples = json.loads(SAMPLE_PATH.read_text(encoding='utf-8'))
        pinyin_by_sample = {
            tokens[0]: tokens[1:]
            for block in SAMPLE_PATH.with_name('pinyin-v1.txt').read_text(encoding='utf-8').strip().split('\n\n')
            if (tokens := block.split())
        }

        for grade, speeds_by_language in TRIAL_SPEEDS.items():
            for sample in samples:
                language = sample['id'].split('-', 1)[0]
                article, _ = TypingArticle.objects.get_or_create(
                    source=SAMPLE_SOURCE, source_id=f'{grade}-{sample["id"]}',
                )
                paragraphs = sample['paragraphs']
                body = (' ' if language == Language.ENGLISH else '').join(paragraphs)
                original, _ = TypingArticleRevision.objects.get_or_create(
                    article=article, version=1,
                    defaults={
                        'grade': grade,
                        'language': language,
                        'difficulty': sample['difficulty'],
                        'title': sample['title'],
                        'paragraphs': paragraphs,
                        'body_digest': hashlib.sha256(body.encode('utf-8')).hexdigest(),
                        'source_metadata': {'material_type': '原创练习文', 'source_title': '打字练习原创样文 V1'},
                        'review_status': TypingArticleRevision.Review.APPROVED,
                    },
                )
                if sample['id'] in pinyin_by_sample:
                    positions = [index for index, char in enumerate(body) if is_han_character(char)]
                    syllables = pinyin_by_sample[sample['id']]
                    if len(positions) != len(syllables):
                        raise CommandError(f'{sample["id"]} 的拼音和汉字数量不一致。')
                    TypingArticleRevision.objects.get_or_create(
                        article=article, version=2,
                        defaults={
                            'grade': original.grade, 'language': original.language,
                            'difficulty': original.difficulty, 'title': original.title,
                            'paragraphs': original.paragraphs, 'body_digest': original.body_digest,
                            'source_metadata': original.source_metadata, 'review_status': original.review_status,
                            'pinyin': dict(zip(map(str, positions), syllables, strict=True)),
                        },
                    )
            for language, speeds in speeds_by_language.items():
                for difficulty, speed in zip(('基础', '进阶', '挑战'), speeds, strict=True):
                    TypingSpeedRule.objects.get_or_create(
                        grade=grade, language=language, difficulty=difficulty, version='trial-v1',
                        is_trial=True, defaults={'target_per_minute': speed},
                    )

        self.stdout.write(self.style.SUCCESS('已准备七、八年级原创样文和 trial-v1 速度线。'))
