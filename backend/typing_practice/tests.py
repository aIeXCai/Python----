import json
from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from .activities import current_activity
from .article_pool import FORMAL_BANK_SOURCE, require_article_pool
from .models import TypingArticle, TypingArticleRevision, TypingSpeedRule
from .scoring import progress_for, score_for, target_seconds


def bank_record(**changes):
    return {
        'id': 'sample-1',
        'grade': 7,
        'grade_label': '七年级',
        'language': 'en',
        'title': 'Morning',
        'paragraphs': ['Good morning.', 'How are you?'],
        'difficulty_draft': '基础',
        'semester': '上',
        'textbook_series': '试用系列',
        'edition': '试用分册',
        'unit': 'Unit 1',
        'lesson_no': '—',
        'textbook_title_or_topic': 'Greetings',
        'genre': '对话',
        'material_type': '教材主题原创',
        'source_title': '试用来源',
        'source_url': 'https://example.com/source',
        'license_or_permission': '测试材料',
        'edition_check_status': '待核对',
        **changes,
    }


class TypingBankTests(TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.bank_path = Path(folder.name) / 'bank.jsonl'

    def import_bank(self, *records, **options):
        self.bank_path.write_text(''.join(json.dumps(row) + '\n' for row in records), encoding='utf-8')
        stdout = StringIO()
        stderr = options.pop('stderr', StringIO())
        call_command('import_typing_bank', str(self.bank_path), stdout=stdout, stderr=stderr, **options)
        return stdout.getvalue() + stderr.getvalue()

    def test_validation_reports_bad_rows_and_writes_nothing(self):
        stderr = StringIO()
        with self.assertRaises(CommandError):
            self.import_bank(
                bank_record(),
                bank_record(id='sample-2', grade_label='八年级'),
                bank_record(id='sample-3', paragraphs=['This isn’t ASCII.']),
                stderr=stderr,
            )
        self.assertIn('第 2 行', stderr.getvalue())
        self.assertIn('grade 与 grade_label', stderr.getvalue())
        self.assertIn('第 3 行', stderr.getvalue())
        self.assertIn('ASCII', stderr.getvalue())
        self.assertEqual(TypingArticle.objects.count(), 0)

    def test_dry_run_and_repeated_import(self):
        report = self.import_bank(bank_record(lesson_no=0), dry_run=True)
        self.assertIn('新增文章 1', report)
        self.assertFalse(TypingArticle.objects.exists())

        self.import_bank(bank_record(lesson_no=0))
        second_report = self.import_bank(bank_record(lesson_no=0))
        self.assertIn('重复跳过 1', second_report)
        revision = TypingArticleRevision.objects.get()
        self.assertEqual(revision.review_status, 'draft')
        self.assertEqual(revision.body, 'Good morning. How are you?')
        self.assertEqual(revision.source_metadata['lesson_no'], 0)

    def test_draft_difficulty_maps_to_trial_pool(self):
        self.import_bank(bank_record(difficulty_draft='L5 中'))
        revision = TypingArticleRevision.objects.get()
        self.assertEqual(revision.difficulty, '进阶')
        self.assertEqual(revision.source_metadata['difficulty_draft'], 'L5 中')

    def test_changed_source_id_requires_confirmation_and_preserves_versions(self):
        self.import_bank(bank_record())
        initial = TypingArticleRevision.objects.get()
        self.assertNotIn('lesson_no', initial.source_metadata)
        changed = bank_record(paragraphs=['Hello again.'])
        report = self.import_bank(changed)
        self.assertIn('来源 ID 内容变更待核对 1', report)
        self.assertEqual(TypingArticleRevision.objects.count(), 1)
        self.import_bank(changed, accept_revisions=True)
        latest = TypingArticleRevision.objects.get(version=2)
        self.assertEqual(latest.article_id, initial.article_id)
        self.assertEqual(latest.review_status, 'draft')
        self.assertNotEqual(latest.body_digest, initial.body_digest)
        self.import_bank(bank_record(), accept_revisions=True)
        self.assertEqual(TypingArticleRevision.objects.count(), 2)

    def test_article_pool_rejects_drafts_and_previous_approved_revisions(self):
        self.import_bank(bank_record())
        scope = dict(grade=7, language='en', difficulty='基础')
        with self.assertRaisesMessage(ValidationError, '请先补充七年级英文'):
            require_article_pool(**scope)

        initial = TypingArticleRevision.objects.get()
        initial.review_status = 'approved'
        initial.save(update_fields=['review_status'])
        self.import_bank(bank_record(paragraphs=['Hello again.']), accept_revisions=True)
        self.assertEqual(list(require_article_pool(**scope)), [initial])
        latest = TypingArticleRevision.objects.get(version=2)
        latest.review_status = 'approved'
        latest.save(update_fields=['review_status'])
        self.assertEqual(list(require_article_pool(**scope)), [latest])

    def test_original_sample_selection_enforces_grade_language_and_difficulty(self):
        call_command('seed_typing_trial', stdout=StringIO())
        call_command('seed_typing_trial', stdout=StringIO())
        self.assertEqual(TypingArticleRevision.objects.filter(review_status='approved').count(), 28)
        self.assertEqual(TypingSpeedRule.objects.filter(is_trial=True).count(), 12)
        scope = dict(grade=7, language='zh', difficulty='基础')
        pool = require_article_pool(**scope)
        self.assertEqual(pool.count(), 2)
        self.assertEqual(require_article_pool(**scope, article_revision_id=pool.first().pk).count(), 1)
        for other_scope in (dict(scope, grade=8), dict(scope, language='en'), dict(scope, difficulty='进阶')):
            with self.subTest(scope=other_scope):
                with self.assertRaisesMessage(ValidationError, '该文章不在本场'):
                    require_article_pool(**other_scope, article_revision_id=pool.first().pk)


    @override_settings(TYPING_PRACTICE_FORMAL=True)
    def test_formal_release_opens_reviewed_articles_and_preserves_pinyin(self):
        rows = [
            bank_record(id='7-en', edition_check_status='已核对', difficulty_draft='L4 易'),
            bank_record(id='7-zh', language='zh', paragraphs=['七年级训练。'],
                        edition_check_status='已核对', difficulty_draft='L5 中'),
            bank_record(id='8-en', grade=8, grade_label='八年级', edition_check_status='已核对',
                        difficulty_draft='L5 中'),
            bank_record(id='8-zh-mid', grade=8, grade_label='八年级', language='zh',
                        paragraphs=['八年级训练。'], edition_check_status='已核对', difficulty_draft='L5 中'),
            bank_record(id='8-zh-high', grade=8, grade_label='八年级', language='zh',
                        paragraphs=['高难度训练。'], edition_check_status='已核对', difficulty_draft='L6 难'),
            bank_record(id='8-zh-pending', grade=8, grade_label='八年级', language='zh',
                        paragraphs=['继续校对。'], difficulty_draft='L5 中'),
        ]
        self.bank_path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
        for _ in range(2):
            call_command('release_typing_bank', str(self.bank_path), stdout=StringIO())
        released = TypingArticleRevision.objects.filter(article__source=FORMAL_BANK_SOURCE)
        self.assertEqual(released.count(), 6)
        self.assertEqual(released.filter(review_status='approved').count(), 5)
        current = current_activity(8, '1')
        self.assertFalse(current.is_trial)
        self.assertEqual(current.languages['zh']['difficulty'], '进阶')
        self.assertEqual(len(current.languages['zh']['article_ids']), 1)
        self.assertEqual(require_article_pool(grade=7, language='zh', difficulty='基础', pinyin=True).count(), 2)


class TypingScoringTests(SimpleTestCase):
    def test_equal_target_work_matches_across_speeds(self):
        short = target_seconds(language='zh', correct_count=120, target_per_minute=30)
        long = target_seconds(language='zh', correct_count=160, target_per_minute=40)
        english = target_seconds(language='en', correct_count=400, target_per_minute=20)
        self.assertEqual(short, long)
        self.assertEqual(short, english)
        self.assertEqual(score_for(progress_for(short)), Decimal('80.0'))

    def test_sum_of_exact_target_work_at_summit_and_near_summit(self):
        a = target_seconds(language='zh', correct_count=53, target_per_minute=20)
        b = target_seconds(language='zh', correct_count=47, target_per_minute=20)
        self.assertEqual(score_for(progress_for(a + b)), Decimal('100.0'))
        self.assertEqual(score_for(progress_for(Decimal('299.99'))), Decimal('99.9'))
        self.assertEqual(score_for(progress_for(0)), Decimal('0.0'))
        self.assertEqual(score_for(progress_for(600)), Decimal('100.0'))
