"""Step 0 regression locks for the existing AI practice catalog and history."""

import uuid

from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from execution.constants import STATUS_SUCCEEDED, TASK_TYPE_GRADE
from execution.models import ExecutionTask
from users.models import CustomUser

from .models import AUDIENCE_GRADE_ALL, Problem, ProblemAudience, Submission


LEGACY_AI_PROBLEM_IDS = {f'problem{number}' for number in range(1, 10)}


class LegacyAICatalogCompatibilityTest(APITestCase):
    fixtures = ['current_ai_catalog.json']

    def setUp(self):
        self.student = CustomUser.objects.create_user(
            username='step0_catalog_student', password='test-pass', role='student',
            grade='八年级', class_num='1', student_number='01',
        )
        self.token = Token.objects.create(user=self.student)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

    def test_fixture_keeps_exactly_nine_stable_ai_problem_ids(self):
        problems = Problem.objects.filter(course='ai')
        self.assertSetEqual(
            set(problems.values_list('problem_id', flat=True)),
            LEGACY_AI_PROBLEM_IDS,
        )
        self.assertTrue(all(problem.archived_at is None for problem in problems))

    def test_fixture_keeps_eighteen_publication_rules_and_grade_visibility(self):
        self.assertEqual(ProblemAudience.objects.count(), 18)
        visible_ids = set(ProblemAudience.objects.filter(
            scope_type=AUDIENCE_GRADE_ALL,
            grade='八年级',
            class_num='',
            is_active=True,
        ).values_list('problem__problem_id', flat=True))
        self.assertSetEqual(visible_ids, LEGACY_AI_PROBLEM_IDS)

    def test_existing_student_problem_list_still_returns_all_nine_items(self):
        response = self.client.get('/api/ai/problems/?course=ai')
        self.assertEqual(response.status_code, 200)
        self.assertSetEqual(
            {item['problem_id'] for item in response.data},
            LEGACY_AI_PROBLEM_IDS,
        )

    def test_all_catalog_problems_keep_tracked_test_cases(self):
        counts = {
            problem.problem_id: problem.get_test_count()
            for problem in Problem.objects.filter(course='ai')
        }
        self.assertSetEqual(set(counts), LEGACY_AI_PROBLEM_IDS)
        self.assertTrue(all(count >= 1 for count in counts.values()), counts)


class LegacySubmissionAndExecutionCompatibilityTest(TestCase):
    fixtures = ['current_ai_catalog.json']

    def setUp(self):
        self.student = CustomUser.objects.create_user(
            username='step0_history_student', password='test-pass', role='student',
            grade='八年级', class_num='1', student_number='02',
        )
        self.problem = Problem.objects.get(problem_id='problem1')
        self.task = ExecutionTask.objects.create(
            user=self.student,
            problem=self.problem,
            task_type=TASK_TYPE_GRADE,
            status=STATUS_SUCCEEDED,
            code='print("legacy")',
            test_snapshot={
                'schema_version': 1,
                'problem_id': 'problem1',
                'cases': [{'number': 1, 'input': '', 'output': 'legacy'}],
            },
            snapshot_hash='a' * 64,
            limits={'memory_mb': 128},
            idempotency_key=str(uuid.uuid4()),
            expires_at=timezone.now() + timezone.timedelta(minutes=5),
            stdout='legacy\n',
            result_detail={'tests': [{'number': 1, 'status': 'passed'}]},
            score=100.0,
            finished_at=timezone.now(),
        )
        self.submission = Submission.objects.create(
            user=self.student,
            problem=self.problem,
            code='print("legacy")',
            score=100.0,
            status='accepted',
            execution_task=self.task,
        )

    def test_legacy_submission_fields_and_task_relation_round_trip(self):
        submission = Submission.objects.select_related('execution_task', 'problem').get(
            pk=self.submission.pk,
        )
        self.assertEqual(submission.user_id, self.student.pk)
        self.assertEqual(submission.problem.problem_id, 'problem1')
        self.assertEqual(submission.code, 'print("legacy")')
        self.assertEqual(submission.score, 100.0)
        self.assertEqual(submission.status, 'accepted')
        self.assertEqual(submission.execution_task.public_id, self.task.public_id)
        self.assertEqual(submission.execution_task.test_snapshot['problem_id'], 'problem1')

    def test_problem_remains_protected_by_legacy_submission(self):
        with self.assertRaises(ProtectedError):
            self.problem.delete()
        self.assertTrue(Problem.objects.filter(pk=self.problem.pk).exists())
        self.assertTrue(Submission.objects.filter(pk=self.submission.pk).exists())
        self.assertTrue(ExecutionTask.objects.filter(pk=self.task.pk).exists())
