"""Step 6 tests for AI quiz submission, settlement, scoring, and recovery."""

import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from unittest import skipUnless

from django.core.management import call_command
from django.db import connection, connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase
from unittest.mock import patch

from execution.constants import STATUS_RUNNING, STATUS_SYSTEM_ERROR
from execution.models import ExecutionTask
from execution.queue import complete_task
from users.models import CustomUser

from ..models import AIChoiceQuestion, AIQuizAttempt, AIQuizSession, AIUnit, Problem, Submission
from ..quizzes.services import blueprint_digest, create_quiz, publish_quiz
from ..quizzes.settlement_services import request_settlement


@override_settings(CODE_EXECUTION_ENABLED=True, EXECUTION_USER_QUEUED_LIMIT=20)
class AIQuizSettlementStep6APITest(APITestCase):
    def setUp(self):
        self.teacher = CustomUser.objects.create_user(
            username='step6_teacher', password='test123', role='teacher',
            managed_grade='七年级',
        )
        self.student = CustomUser.objects.create_user(
            username='step6_student', password='test123', role='student',
            grade='七年级', class_num='1', student_number='01',
        )
        self.other = CustomUser.objects.create_user(
            username='step6_other', password='test123', role='student',
            grade='七年级', class_num='1', student_number='02',
        )
        self.root = AIUnit.objects.create(
            grade='七年级', name='step6-root', display_name='AI 综合',
            created_by=self.teacher,
        )
        self.section = AIUnit.objects.create(
            grade='七年级', parent=self.root, name='step6-section',
            display_name='综合应用', created_by=self.teacher,
        )
        for index, difficulty in enumerate(('easy', 'medium'), 1):
            AIChoiceQuestion.objects.create(
                unit=self.section, difficulty=difficulty, category='综合',
                text=f'选择题 {index}', option_a='正确', option_b='错误B',
                option_c='错误C', option_d='错误D', answer='A',
                explanation=f'解析 {index}', created_by=self.teacher,
            )
        self.problems = [
            Problem.objects.create(
                problem_id=f'step6_problem_{index}', title=f'编程题 {index}',
                description=f'完成第 {index} 题', template_code=f'print({index})',
                difficulty='easy', grade_tag='七年级', unit=self.section,
                course='ai', created_by=self.teacher,
            )
            for index in (1, 2)
        ]

    def _auth(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        return {'HTTP_AUTHORIZATION': f'Token {token.key}'}

    def _publish(self, *, choice_points='30.0', programming=True, title='Step 6 混合小测'):
        programming_items = []
        if programming:
            item_points = '35.0' if Decimal(choice_points) > 0 else '50.0'
            programming_items = [
                {'problem_id': problem.problem_id, 'position': index, 'points': item_points}
                for index, problem in enumerate(self.problems, 1)
            ]
        choice_count = 2 if Decimal(choice_points) > 0 else 0
        values = {
            'title': title,
            'content_grade': '七年级',
            'choice_unit_ids': [self.section.pk] if choice_count else [],
            'choice_question_count': choice_count,
            'choice_difficulty_ratio': {
                'easy': 1 if choice_count else 0,
                'medium': 1 if choice_count else 0,
                'hard': 0,
            },
            'choice_points': choice_points,
            'programming_items': programming_items,
            'time_limit': 30,
            'audience': [{'scope_type': 'grade_all', 'grade': '七年级'}],
        }
        session = create_quiz(actor=self.teacher, values=values)
        with patch.object(Problem, 'get_test_cases', return_value=[{
            'number': 8, 'input': 'input', 'output': 'expected',
        }]):
            return publish_quiz(
                actor=self.teacher, session_id=session.pk, expected_version=1,
            )

    def _start(self, session, user=None):
        user = user or self.student
        response = self.client.post(
            f'/api/ai/quizzes/{session.pk}/attempt/', {}, format='json',
            **self._auth(user),
        )
        self.assertIn(response.status_code, (200, 201), response.data)
        return AIQuizAttempt.objects.get(pk=response.data['attempt_id'])

    def _choice_answers(self, attempt, *, correct_count=2):
        choices = [item for item in attempt.snapshot_json['items'] if item['type'] == 'choice']
        answers = {}
        for index, item in enumerate(choices):
            if index < correct_count:
                answers[item['item_id']] = item['correct_display_option']
            else:
                answers[item['item_id']] = next(
                    option for option in 'ABCD' if option != item['correct_display_option']
                )
        return answers

    def _programming_items(self, attempt):
        return [item for item in attempt.snapshot_json['items'] if item['type'] == 'programming']

    def _submit(self, session, attempt, answers=None, revision=0):
        return self.client.post(
            f'/api/ai/quizzes/{session.pk}/attempt/submit/',
            {
                'attempt_id': attempt.pk,
                'revision': revision,
                'answers': answers if answers is not None else {},
            },
            format='json', **self._auth(self.student),
        )

    def _complete_success(self, task):
        token = 'step6-lease-token'
        task.status = STATUS_RUNNING
        task.leased_by = 'step6-runner'
        task.lease_token_hash = hashlib.sha256(token.encode()).hexdigest()
        task.lease_expires_at = timezone.now() + timedelta(minutes=1)
        task.save(update_fields=[
            'status', 'leased_by', 'lease_token_hash', 'lease_expires_at', 'updated_at',
        ])
        result = {
            'status': 'succeeded',
            'stdout': '',
            'stderr': '',
            'execution_ms': 10,
            'score': 100,
            'detail': {'tests': [{
                'number': 1,
                'status': 'passed',
                'actual_output': 'expected',
                'stderr': '',
                'execution_ms': 5,
            }]},
        }
        with self.captureOnCommitCallbacks(execute=True):
            complete_task(
                task_id=task.public_id,
                runner_id='step6-runner',
                lease_token=token,
                result=result,
            )

    def test_pure_choice_submit_scores_and_is_idempotent(self):
        session = self._publish(choice_points='100.0', programming=False, title='纯选择题')
        attempt = self._start(session)
        answers = self._choice_answers(attempt, correct_count=1)
        first = self._submit(session, attempt, answers)
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(first.data['status'], 'submitted')
        self.assertEqual(first.data['scores'], {
            'choice': '50.0', 'programming': '0.0', 'total': '50.0',
        })
        self.assertEqual(first.data['choice_summary']['correct_count'], 1)
        self.assertEqual(len(first.data['choice_items']), 2)
        self.assertIn('explanation', first.data['choice_items'][0])

        repeated = self._submit(session, attempt, {}, revision=999)
        self.assertEqual(repeated.status_code, 200, repeated.data)
        self.assertEqual(repeated.data['scores']['total'], '50.0')
        attempt.refresh_from_db()
        self.assertEqual(attempt.result_revision, 1)

    def test_mixed_scoring_uses_each_items_highest_valid_submission(self):
        session = self._publish()
        attempt = self._start(session)
        items = self._programming_items(attempt)
        for score in (40, 80):
            Submission.objects.create(
                user=self.student, problem=self.problems[0], code=f'score {score}',
                score=score, status='wrong_answer', quiz_attempt=attempt,
                quiz_item_id=items[0]['item_id'],
            )
        Submission.objects.create(
            user=self.student, problem=self.problems[1], code='perfect',
            score=100, status='accepted', quiz_attempt=attempt,
            quiz_item_id=items[1]['item_id'],
        )
        response = self._submit(session, attempt, self._choice_answers(attempt, correct_count=1))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['scores'], {
            'choice': '15.0', 'programming': '63.0', 'total': '78.0',
        })
        self.assertEqual(
            [item['best_score'] for item in response.data['programming_items']],
            [80.0, 100.0],
        )
        self.assertEqual(
            [item['submission_count'] for item in response.data['programming_items']],
            [2, 1],
        )
        self.assertTrue(response.data['can_retry'])

    def test_submit_waits_for_grade_and_runner_hook_finalizes(self):
        session = self._publish(choice_points='0.0', title='纯编程题')
        attempt = self._start(session)
        item = self._programming_items(attempt)[0]
        queued = self.client.post(
            f'/api/ai/quizzes/{session.pk}/attempt/items/{item["item_id"]}/submit/',
            {'attempt_id': attempt.pk, 'code': 'print(1)'},
            format='json', **self._auth(self.student),
        )
        task = ExecutionTask.objects.get(public_id=queued.data['task_id'])
        locked = self._submit(session, attempt)
        self.assertEqual(locked.status_code, 200, locked.data)
        self.assertEqual(locked.data['status'], 'settling')
        self.assertIsNone(locked.data['scores']['total'])

        self._complete_success(task)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, AIQuizAttempt.STATUS_SUBMITTED)
        self.assertEqual(str(attempt.programming_score), '50.0')
        result = self.client.get(
            f'/api/ai/quizzes/{session.pk}/result/', **self._auth(self.student),
        )
        self.assertEqual(result.data['scores']['total'], '50.0')

    def test_system_error_is_an_issue_not_a_fake_student_score(self):
        session = self._publish(choice_points='0.0')
        attempt = self._start(session)
        item = self._programming_items(attempt)[0]
        task = ExecutionTask.objects.create(
            user=self.student, problem=self.problems[0], quiz_attempt=attempt,
            quiz_item_id=item['item_id'], task_type='grade', status=STATUS_SYSTEM_ERROR,
            code='broken', test_snapshot={'schema_version': 1, 'problem_id': self.problems[0].problem_id, 'cases': []},
            snapshot_hash='b' * 64, limits={}, idempotency_key=str(uuid.uuid4()),
            expires_at=timezone.now() + timedelta(minutes=1),
        )
        Submission.objects.create(
            user=self.student, problem=self.problems[0], code='broken', score=None,
            status='error', execution_task=task, quiz_attempt=attempt,
            quiz_item_id=item['item_id'],
        )
        response = self._submit(session, attempt)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['grading_issue_count'], 1)
        self.assertEqual(response.data['programming_items'][0]['status'], 'system_issue')
        self.assertIsNone(response.data['programming_items'][0]['best_score'])
        self.assertEqual(response.data['scores']['programming'], '0.0')

    def test_result_query_lazily_settles_expired_attempt(self):
        session = self._publish(choice_points='100.0', programming=False)
        attempt = self._start(session)
        attempt.deadline_at = timezone.now() - timedelta(seconds=1)
        attempt.save(update_fields=['deadline_at'])
        response = self.client.get(
            f'/api/ai/quizzes/{session.pk}/result/', **self._auth(self.student),
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['status'], 'timed_out')
        self.assertEqual(response.data['final_reason'], 'timed_out')
        self.assertEqual(response.data['scores']['total'], '0.0')

    def test_grade_accepted_before_deadline_finishes_and_counts_after_timeout(self):
        session = self._publish(choice_points='0.0')
        attempt = self._start(session)
        item = self._programming_items(attempt)[0]
        queued = self.client.post(
            f'/api/ai/quizzes/{session.pk}/attempt/items/{item["item_id"]}/submit/',
            {'attempt_id': attempt.pk, 'code': 'print(1)'},
            format='json', **self._auth(self.student),
        )
        task = ExecutionTask.objects.get(public_id=queued.data['task_id'])
        attempt.deadline_at = timezone.now() - timedelta(seconds=1)
        attempt.save(update_fields=['deadline_at'])
        waiting = self.client.get(
            f'/api/ai/quizzes/{session.pk}/result/', **self._auth(self.student),
        )
        self.assertEqual(waiting.data['status'], 'settling')
        self.assertEqual(waiting.data['final_reason'], 'timed_out')
        self._complete_success(task)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, AIQuizAttempt.STATUS_TIMED_OUT)
        self.assertEqual(str(attempt.total_score), '50.0')

    def test_close_requests_settlement_and_closed_result_remains_visible(self):
        session = self._publish(choice_points='100.0', programming=False)
        attempt = self._start(session)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f'/api/ai/admin/quizzes/{session.pk}/close/',
                {'expected_version': 2}, format='json', **self._auth(self.teacher),
            )
        self.assertEqual(response.status_code, 200, response.data)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, AIQuizAttempt.STATUS_CLOSED)
        result = self.client.get(
            f'/api/ai/quizzes/{session.pk}/result/', **self._auth(self.student),
        )
        self.assertEqual(result.status_code, 200, result.data)
        listed = self.client.get('/api/ai/quizzes/', **self._auth(self.student))
        self.assertEqual(listed.data[0]['action'], 'result')

    def test_teacher_can_reset_final_attempt_and_student_starts_attempt_two(self):
        session = self._publish(choice_points='100.0', programming=False)
        attempt = self._start(session)
        self._submit(session, attempt, self._choice_answers(attempt))
        reset = self.client.post(
            f'/api/ai/admin/quizzes/{session.pk}/attempts/{attempt.pk}/reset/',
            {'reason': '课堂网络异常'}, format='json', **self._auth(self.teacher),
        )
        self.assertEqual(reset.status_code, 200, reset.data)
        self.assertEqual(reset.data['status'], 'reset')
        second = self._start(session)
        self.assertEqual(second.attempt_no, 2)
        attempt.refresh_from_db()
        self.assertIsNone(attempt.current_marker)

    def test_system_issue_regrade_recalculates_and_increments_revision(self):
        session = self._publish(choice_points='0.0')
        attempt = self._start(session)
        item = self._programming_items(attempt)[0]
        failed_task = ExecutionTask.objects.create(
            user=self.student, problem=self.problems[0], quiz_attempt=attempt,
            quiz_item_id=item['item_id'], task_type='grade', status=STATUS_SYSTEM_ERROR,
            code='print(1)', test_snapshot=session.blueprint_json['programming_items'][0]['test_snapshot'],
            snapshot_hash='c' * 64, limits={}, idempotency_key=str(uuid.uuid4()),
            expires_at=timezone.now() + timedelta(minutes=1),
        )
        failed = Submission.objects.create(
            user=self.student, problem=self.problems[0], code='print(1)', score=None,
            status='error', execution_task=failed_task, quiz_attempt=attempt,
            quiz_item_id=item['item_id'],
        )
        self._submit(session, attempt)
        attempt.refresh_from_db()
        self.assertEqual(attempt.result_revision, 1)
        key = str(uuid.uuid4())
        regrade = self.client.post(
            f'/api/ai/admin/quizzes/{session.pk}/attempts/{attempt.pk}/items/{item["item_id"]}/regrade/',
            {}, format='json', HTTP_IDEMPOTENCY_KEY=key, **self._auth(self.teacher),
        )
        self.assertEqual(regrade.status_code, 202, regrade.data)
        new_submission = Submission.objects.get(pk=regrade.data['submission_id'])
        self.assertEqual(new_submission.regrade_of, failed)
        self.assertEqual(new_submission.code, failed.code)
        repeated = self.client.post(
            f'/api/ai/admin/quizzes/{session.pk}/attempts/{attempt.pk}/items/{item["item_id"]}/regrade/',
            {}, format='json', HTTP_IDEMPOTENCY_KEY=key, **self._auth(self.teacher),
        )
        self.assertEqual(repeated.status_code, 202, repeated.data)
        self.assertEqual(repeated.data['task_id'], regrade.data['task_id'])
        self.assertFalse(repeated.data['created'])
        self._complete_success(new_submission.execution_task)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, AIQuizAttempt.STATUS_SUBMITTED)
        self.assertEqual(attempt.result_revision, 2)
        self.assertEqual(attempt.grading_issue_count, 0)
        self.assertEqual(str(attempt.total_score), '50.0')

    def test_management_command_compensates_overdue_attempt_and_history_is_owner_scoped(self):
        session = self._publish(choice_points='100.0', programming=False)
        attempt = self._start(session)
        attempt.deadline_at = timezone.now() - timedelta(seconds=1)
        attempt.save(update_fields=['deadline_at'])
        call_command('settle_ai_quiz_attempts', verbosity=0)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, AIQuizAttempt.STATUS_TIMED_OUT)
        history = self.client.get(
            f'/api/ai/quizzes/{session.pk}/attempts/', **self._auth(self.student),
        )
        self.assertEqual(history.status_code, 200, history.data)
        self.assertEqual(history.data[0]['attempt_id'], attempt.pk)
        denied = self.client.get(
            f'/api/ai/quizzes/{session.pk}/attempts/', **self._auth(self.other),
        )
        self.assertEqual(denied.status_code, 404)


@skipUnless(connection.vendor == 'mysql', 'MySQL/InnoDB concurrency integration test')
class AIQuizSettlementMySQLConcurrencyTest(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.student = CustomUser.objects.create_user(
            username='step6_concurrent_student', password='test123', role='student',
            grade='七年级', class_num='1', student_number='01',
        )
        blueprint = {
            'schema_version': 1,
            'session': {
                'title': '并发交卷', 'content_grade': '七年级', 'time_limit': 30,
                'choice_question_count': 0,
                'choice_difficulty_ratio': {'easy': 0, 'medium': 0, 'hard': 0},
                'choice_points': '0.0',
            },
            'choice_pool': [],
            'programming_items': [],
        }
        digest = blueprint_digest(blueprint)
        teacher = CustomUser.objects.create_user(
            username='step6_concurrent_teacher', password='test123', role='teacher',
            managed_grade='七年级',
        )
        self.session = AIQuizSession.objects.create(
            title='并发交卷', content_grade='七年级', created_by=teacher,
            status=AIQuizSession.STATUS_OPEN, blueprint_version=1,
            blueprint_json=blueprint, blueprint_hash=digest,
        )
        self.attempt = AIQuizAttempt.objects.create(
            user=self.student, session=self.session,
            snapshot_json={
                'schema_version': 1,
                'session_id': self.session.pk,
                'blueprint_hash': digest,
                'session': {'title': '并发交卷', 'choice_points': '0.0'},
                'items': [],
            },
        )

    def _submit(self, _index):
        connections.close_all()
        user = CustomUser.objects.get(pk=self.student.pk)
        result = request_settlement(
            user=user,
            session_id=self.session.pk,
            attempt_id=self.attempt.pk,
            reason='submitted',
            final_answers={},
            revision=0,
        )
        status_value = result.status
        connections.close_all()
        return status_value

    def test_concurrent_submit_finalizes_once(self):
        with ThreadPoolExecutor(max_workers=6) as executor:
            statuses = list(executor.map(self._submit, range(6)))
        self.assertEqual(set(statuses), {AIQuizAttempt.STATUS_SUBMITTED})
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.result_revision, 1)
