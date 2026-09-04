from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from ai_courses.models import Problem, Submission
from execution.constants import STATUS_QUEUED, TASK_TYPE_GRADE, TASK_TYPE_RUN
from execution.models import ExecutionTask, RunnerNode
from users.models import CustomUser


class ExecutionModelTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='runner_model_student',
            password='test-password',
            role='student',
            grade='七年级',
            class_num='1',
            student_number='01',
        )
        self.problem = Problem.objects.create(
            problem_id='runner_model_problem',
            title='Runner 模型测试题',
        )

    def make_task(self, **overrides):
        values = {
            'user': self.user,
            'problem': self.problem,
            'task_type': TASK_TYPE_RUN,
            'code': "print('ok')",
            'stdin': '',
            'snapshot_hash': 'a' * 64,
            'limits': {'wall_seconds': 10},
            'idempotency_key': 'run-request-1',
            'expires_at': timezone.now() + timedelta(minutes=2),
        }
        values.update(overrides)
        return ExecutionTask.objects.create(**values)

    def test_task_defaults_to_queued_with_public_uuid(self):
        task = self.make_task()

        self.assertEqual(task.status, STATUS_QUEUED)
        self.assertIsNotNone(task.public_id)
        self.assertEqual(task.attempt_count, 0)
        self.assertEqual(task.result_detail, {})

    def test_idempotency_key_is_unique_per_user(self):
        self.make_task()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.make_task(code="print('duplicate')")

        other = CustomUser.objects.create_user(
            username='runner_model_student_2',
            password='test-password',
            role='student',
            grade='七年级',
            class_num='1',
            student_number='02',
        )
        task = self.make_task(user=other)
        self.assertEqual(task.user, other)

    def test_database_rejects_score_outside_percentage_range(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.make_task(score=101)

    def test_problem_deletion_keeps_task_snapshot_record(self):
        task = self.make_task()
        self.problem.delete()

        task.refresh_from_db()
        self.assertIsNone(task.problem)

    def test_submission_can_wait_without_score_and_link_to_task(self):
        task = self.make_task(
            task_type=TASK_TYPE_GRADE,
            idempotency_key='grade-request-1',
            test_snapshot={'cases': [{'input': '1', 'output': '1'}]},
        )
        submission = Submission.objects.create(
            user=self.user,
            problem=self.problem,
            code="print(input())",
            score=None,
            status='pending',
            execution_task=task,
        )

        self.assertIsNone(submission.score)
        self.assertEqual(task.submission, submission)


class RunnerNodeModelTest(TestCase):
    def test_runner_node_stores_health_metadata_without_secret(self):
        node = RunnerNode.objects.create(
            runner_id='local-runner-1',
            protocol_version='runner.v1',
            sandbox_image_digest='sha256:' + ('b' * 64),
            capacity=2,
            active_slots=1,
            status='online',
            last_heartbeat_at=timezone.now(),
        )

        self.assertEqual(str(node), 'local-runner-1')
        field_names = {field.name for field in RunnerNode._meta.fields}
        self.assertNotIn('secret', field_names)
        self.assertNotIn('service_secret', field_names)
