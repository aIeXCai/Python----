"""Step 5 tests for programming execution inside immutable AI quiz attempts."""

import uuid
from datetime import timedelta
from unittest.mock import patch

from django.test import override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from execution.constants import STATUS_SUCCEEDED
from execution.models import ExecutionTask, RunnerNode
from users.models import CustomUser

from ..models import AIQuizAttempt, AIUnit, Problem, Submission
from ..quizzes.services import create_quiz, publish_quiz


@override_settings(CODE_EXECUTION_ENABLED=True, EXECUTION_USER_QUEUED_LIMIT=20)
class AIQuizProgrammingStep5APITest(APITestCase):
    def setUp(self):
        self.teacher = CustomUser.objects.create_user(
            username='step5_teacher', password='test123', role='teacher',
            managed_grade='七年级',
        )
        self.student = CustomUser.objects.create_user(
            username='step5_student', password='test123', role='student',
            grade='七年级', class_num='1', student_number='01',
        )
        self.other = CustomUser.objects.create_user(
            username='step5_other', password='test123', role='student',
            grade='七年级', class_num='1', student_number='02',
        )
        self.root = AIUnit.objects.create(
            grade='七年级', name='step5-root', display_name='AI 编程',
            created_by=self.teacher,
        )
        self.section = AIUnit.objects.create(
            grade='七年级', parent=self.root, name='step5-section',
            display_name='顺序结构', created_by=self.teacher,
        )
        self.problems = [
            Problem.objects.create(
                problem_id=f'step5_problem_{index}', title=f'编程题 {index}',
                description=f'请完成第 {index} 题', template_code=f'print({index})',
                difficulty='easy', grade_tag='七年级', unit=self.section,
                course='ai', created_by=self.teacher,
            )
            for index in (1, 2)
        ]
        values = {
            'title': 'Step 5 编程小测',
            'content_grade': '七年级',
            'choice_unit_ids': [],
            'choice_question_count': 0,
            'choice_difficulty_ratio': {'easy': 0, 'medium': 0, 'hard': 0},
            'choice_points': '0.0',
            'programming_items': [
                {'problem_id': problem.problem_id, 'position': index, 'points': '50.0'}
                for index, problem in enumerate(self.problems, 1)
            ],
            'time_limit': 30,
            'audience': [{'scope_type': 'grade_all', 'grade': '七年级'}],
        }
        self.session = create_quiz(actor=self.teacher, values=values)
        frozen_cases = [{'number': 9, 'input': 'frozen input', 'output': 'frozen output'}]
        with patch.object(Problem, 'get_test_cases', return_value=frozen_cases):
            self.session = publish_quiz(
                actor=self.teacher, session_id=self.session.pk, expected_version=1,
            )
        self.attempt = self._start(self.student)
        self.items = [
            item for item in self.attempt.snapshot_json['items']
            if item['type'] == 'programming'
        ]

    def _auth(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        return {'HTTP_AUTHORIZATION': f'Token {token.key}'}

    def _start(self, user):
        response = self.client.post(
            f'/api/ai/quizzes/{self.session.pk}/attempt/', {}, format='json',
            **self._auth(user),
        )
        self.assertIn(response.status_code, (200, 201), response.data)
        return AIQuizAttempt.objects.get(pk=response.data['attempt_id'])

    def _url(self, item_id, suffix=''):
        return f'/api/ai/quizzes/{self.session.pk}/attempt/items/{item_id}/{suffix}'

    def test_item_detail_is_allowlisted_and_reports_best_valid_score(self):
        item = self.items[0]
        Submission.objects.create(
            user=self.student, problem=self.problems[0], code='old', score=40,
            status='wrong_answer', quiz_attempt=self.attempt,
            quiz_item_id=item['item_id'],
        )
        Submission.objects.create(
            user=self.student, problem=self.problems[0], code='best', score=80,
            status='wrong_answer', quiz_attempt=self.attempt,
            quiz_item_id=item['item_id'],
        )
        response = self.client.get(self._url(item['item_id']), **self._auth(self.student))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['best_score'], 80)
        self.assertEqual(response.data['description'], item['description'])
        self.assertEqual(response.data['template_code'], item['template_code'])
        body = str(response.data)
        for secret in ('test_snapshot', 'test_snapshot_hash', 'source_problem_id', 'cases'):
            self.assertNotIn(secret, body)

    def test_run_is_idempotent_and_active_task_can_be_recovered(self):
        item = self.items[0]
        key = str(uuid.uuid4())
        payload = {'attempt_id': self.attempt.pk, 'code': 'print(1)', 'stdin': 'abc'}
        first = self.client.post(
            self._url(item['item_id'], 'run/'), payload, format='json',
            HTTP_IDEMPOTENCY_KEY=key, **self._auth(self.student),
        )
        second = self.client.post(
            self._url(item['item_id'], 'run/'), payload, format='json',
            HTTP_IDEMPOTENCY_KEY=key, **self._auth(self.student),
        )
        self.assertEqual(first.status_code, 202, first.data)
        self.assertEqual(first.data['task_id'], second.data['task_id'])
        self.assertFalse(second.data['created'])
        task = ExecutionTask.objects.get(public_id=first.data['task_id'])
        self.assertEqual(task.quiz_attempt, self.attempt)
        self.assertEqual(task.quiz_item_id, item['item_id'])
        self.assertIsNone(getattr(task, 'submission', None))

        active = self.client.get(
            self._url(item['item_id'], 'executions/active/'),
            {'attempt_id': self.attempt.pk, 'task_type': 'run'},
            **self._auth(self.student),
        )
        self.assertEqual(active.status_code, 200, active.data)
        self.assertEqual(active.data['task_id'], first.data['task_id'])

    def test_grade_uses_publish_time_snapshot_and_binds_submission_context(self):
        item = self.items[0]
        with patch.object(Problem, 'get_test_cases', return_value=[{
            'number': 1, 'input': 'changed', 'output': 'changed',
        }]):
            response = self.client.post(
                self._url(item['item_id'], 'submit/'),
                {'attempt_id': self.attempt.pk, 'code': 'print("answer")'},
                format='json', **self._auth(self.student),
            )
        self.assertEqual(response.status_code, 202, response.data)
        task = ExecutionTask.objects.get(public_id=response.data['task_id'])
        submission = Submission.objects.get(pk=response.data['submission_id'])
        self.assertEqual(task.test_snapshot['cases'][0]['input'], 'frozen input')
        self.assertEqual(task.test_snapshot['cases'][0]['output'], 'frozen output')
        self.assertEqual(task.quiz_attempt, self.attempt)
        self.assertEqual(task.quiz_item_id, item['item_id'])
        self.assertEqual(submission.quiz_attempt, self.attempt)
        self.assertEqual(submission.quiz_item_id, item['item_id'])
        self.assertTrue(submission.counts_for_quiz)
        self.assertNotIn('test_snapshot', str(response.data))

    def test_multiple_programming_items_create_independent_grade_records(self):
        responses = []
        for index, item in enumerate(self.items, 1):
            responses.append(self.client.post(
                self._url(item['item_id'], 'submit/'),
                {'attempt_id': self.attempt.pk, 'code': f'print({index})'},
                format='json', **self._auth(self.student),
            ))
        self.assertTrue(all(response.status_code == 202 for response in responses))
        submissions = Submission.objects.filter(quiz_attempt=self.attempt)
        self.assertEqual(submissions.count(), 2)
        self.assertEqual(
            set(submissions.values_list('quiz_item_id', flat=True)),
            {item['item_id'] for item in self.items},
        )

    def test_attempt_and_item_context_cannot_be_crossed(self):
        other_attempt = self._start(self.other)
        item = self.items[0]
        crossed_attempt = self.client.post(
            self._url(item['item_id'], 'run/'),
            {'attempt_id': other_attempt.pk, 'code': 'print(1)'},
            format='json', **self._auth(self.student),
        )
        self.assertEqual(crossed_attempt.status_code, 404)
        self.assertEqual(crossed_attempt.data['code'], 'attempt_not_found')
        unknown_item = self.client.post(
            self._url(str(uuid.uuid4()), 'run/'),
            {'attempt_id': self.attempt.pk, 'code': 'print(1)'},
            format='json', **self._auth(self.student),
        )
        self.assertEqual(unknown_item.status_code, 404)
        self.assertEqual(unknown_item.data['code'], 'unknown_quiz_item')
        self.assertEqual(ExecutionTask.objects.count(), 0)

    @override_settings(EXECUTION_USER_QUEUED_LIMIT=1)
    def test_quiz_and_legacy_practice_share_capacity_without_changing_legacy_context(self):
        legacy = ExecutionTask.objects.create(
            user=self.student, task_type='run', code='legacy', snapshot_hash='a' * 64,
            limits={}, idempotency_key=str(uuid.uuid4()),
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        self.assertIsNone(legacy.quiz_attempt)
        self.assertEqual(legacy.quiz_item_id, '')
        response = self.client.post(
            self._url(self.items[0]['item_id'], 'run/'),
            {'attempt_id': self.attempt.pk, 'code': 'print(1)'},
            format='json', **self._auth(self.student),
        )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data['code'], 'queue_limit_reached')

    def test_deadline_is_enforced_before_enqueue(self):
        self.attempt.deadline_at = timezone.now() - timedelta(seconds=1)
        self.attempt.save(update_fields=['deadline_at'])
        response = self.client.post(
            self._url(self.items[0]['item_id'], 'submit/'),
            {'attempt_id': self.attempt.pk, 'code': 'print(1)'},
            format='json', **self._auth(self.student),
        )
        self.assertEqual(response.status_code, 410, response.data)
        self.assertEqual(response.data['code'], 'quiz_deadline_passed')
        self.assertEqual(ExecutionTask.objects.count(), 0)
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, AIQuizAttempt.STATUS_SETTLING)

    def test_completed_task_detail_still_uses_existing_safe_execution_contract(self):
        item = self.items[0]
        response = self.client.post(
            self._url(item['item_id'], 'run/'),
            {'attempt_id': self.attempt.pk, 'code': 'print(1)'},
            format='json', **self._auth(self.student),
        )
        ExecutionTask.objects.filter(public_id=response.data['task_id']).update(
            status=STATUS_SUCCEEDED, stdout='1\n', finished_at=timezone.now(),
        )
        detail = self.client.get(
            f"/api/ai/executions/{response.data['task_id']}/", **self._auth(self.student),
        )
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertEqual(detail.data['output'], '1\n')
        self.assertNotIn('code', detail.data)
        self.assertNotIn('test_snapshot', detail.data)

    @override_settings(EXECUTION_REQUIRE_HEALTHY_RUNNER=True)
    def test_quiz_submit_rejects_without_runner_and_creates_no_submission(self):
        RunnerNode.objects.all().delete()
        response = self.client.post(
            self._url(self.items[0]['item_id'], 'submit/'),
            {'attempt_id': self.attempt.pk, 'code': 'print(1)'},
            format='json', **self._auth(self.student),
        )
        self.assertEqual(response.status_code, 503, response.data)
        self.assertEqual(response.data['code'], 'runner_unavailable')
        self.assertEqual(ExecutionTask.objects.count(), 0)
        self.assertEqual(Submission.objects.filter(quiz_attempt=self.attempt).count(), 0)
