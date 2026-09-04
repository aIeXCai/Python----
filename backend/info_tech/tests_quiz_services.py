from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless

from django.db import IntegrityError, connection, connections, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from users.models import CustomUser
from .models import Question, QuizSession, QuizSubmission, Unit
from .quiz_services import start_or_resume_attempt, submit_attempt
from .quiz_snapshot import student_snapshot_questions


class QuizIntegrityModelAndServiceTest(TestCase):
    def setUp(self):
        self.teacher = CustomUser.objects.create_user(
            username='service-teacher', password='test', role='teacher', managed_grade='七年级',
        )
        self.student = CustomUser.objects.create_user(
            username='service-student', password='test', role='student', grade='七年级',
            class_num='1', student_number='01',
        )
        unit = Unit.objects.create(grade='七年级', name='service', display_name='服务测试')
        Question.objects.create(
            unit=unit, text='服务题', difficulty='easy', answer='A', explanation='秘密解析',
            option_a='正确', option_b='错误B', option_c='错误C', option_d='错误D',
        )
        self.session = QuizSession.objects.create(
            title='服务小测', created_by=self.teacher, num_questions=1,
            difficulty_ratio={'easy': 1}, time_limit=10, status='open',
            opened_at=timezone.now(), visible_grades=['七年级'],
        )
        self.session.units.add(unit)

    def test_snapshot_keeps_secrets_server_side_but_student_serializer_drops_them(self):
        attempt, created = start_or_resume_attempt(self.student, self.session.pk)
        self.assertTrue(created)
        item = attempt.snapshot_json['questions'][0]
        self.assertIn('correct_option', item)
        self.assertIn('explanation', item)
        visible = student_snapshot_questions(attempt.snapshot_json)[0]
        self.assertNotIn('correct_option', visible)
        self.assertNotIn('explanation', visible)
        self.assertNotIn('source_question_id', visible)

    def test_database_rejects_two_current_attempts_but_allows_history(self):
        attempt, _ = start_or_resume_attempt(self.student, self.session.pk)
        with self.assertRaises(IntegrityError), transaction.atomic():
            QuizSubmission.objects.create(
                user=self.student, session=self.session, grade='七年级',
                attempt_no=2, current_marker=True, status='in_progress',
                snapshot_version=1, snapshot_json=attempt.snapshot_json,
                answers_json='{}', started_at=timezone.now(), submitted_at=None,
            )
        attempt.current_marker = None
        attempt.status = 'reset'
        attempt.save(update_fields=['current_marker', 'status'])
        replacement = QuizSubmission.objects.create(
            user=self.student, session=self.session, grade='七年级',
            attempt_no=2, current_marker=True, status='in_progress',
            snapshot_version=1, snapshot_json=attempt.snapshot_json,
            answers_json='{}', started_at=timezone.now(), submitted_at=None,
        )
        self.assertEqual(replacement.attempt_no, 2)


@skipUnless(connection.vendor == 'mysql', 'MySQL/InnoDB concurrency integration test')
class QuizAttemptMySQLConcurrencyTest(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.teacher = CustomUser.objects.create_user(
            username='concurrent-teacher', password='test', role='teacher', managed_grade='七年级',
        )
        self.student = CustomUser.objects.create_user(
            username='concurrent-student', password='test', role='student', grade='七年级',
            class_num='1', student_number='01',
        )
        unit = Unit.objects.create(grade='七年级', name='concurrent', display_name='并发测试')
        Question.objects.create(
            unit=unit, text='并发题', difficulty='easy', answer='A', explanation='解析',
            option_a='A', option_b='B', option_c='C', option_d='D',
        )
        self.session = QuizSession.objects.create(
            title='并发小测', created_by=self.teacher, num_questions=1,
            difficulty_ratio={'easy': 1}, time_limit=10, status='open',
            opened_at=timezone.now(), visible_grades=['七年级'],
        )
        self.session.units.add(unit)

    def _start(self, _):
        connections.close_all()
        student = CustomUser.objects.get(pk=self.student.pk)
        attempt, _created = start_or_resume_attempt(student, self.session.pk)
        attempt_id = attempt.pk
        connections.close_all()
        return attempt_id

    def _submit(self, payload):
        connections.close_all()
        student = CustomUser.objects.get(pk=self.student.pk)
        attempt = submit_attempt(student, self.session.pk, **payload)
        result = (attempt.pk, attempt.score, attempt.submitted_at)
        connections.close_all()
        return result

    def test_ten_concurrent_starts_and_submits_produce_one_current_result(self):
        with ThreadPoolExecutor(max_workers=10) as executor:
            attempt_ids = list(executor.map(self._start, range(10)))
        self.assertEqual(len(set(attempt_ids)), 1)
        self.assertEqual(
            QuizSubmission.objects.filter(
                user=self.student, session=self.session, current_marker=True,
            ).count(),
            1,
        )

        attempt = QuizSubmission.objects.get(pk=attempt_ids[0])
        item = attempt.snapshot_json['questions'][0]
        payload = {
            'attempt_id': attempt.pk,
            'revision': 0,
            'answers': {item['item_id']: item['correct_option']},
        }
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(self._submit, [payload] * 10))
        self.assertEqual(len(set(results)), 1)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, QuizSubmission.STATUS_SUBMITTED)
        self.assertEqual(attempt.score, 100.0)
