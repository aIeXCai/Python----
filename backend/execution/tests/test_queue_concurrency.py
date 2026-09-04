import threading
import uuid
from datetime import timedelta

from django.db import close_old_connections
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone

from execution.constants import STATUS_RUNNING, TASK_TYPE_RUN
from execution.models import ExecutionTask, RunnerNode
from execution.queue import claim_task
from users.models import CustomUser


@skipUnlessDBFeature('has_select_for_update_skip_locked')
class MySQLQueueConcurrencyTest(TransactionTestCase):
    reset_sequences = True

    def make_task(self, index, *, user=None):
        user = user or CustomUser.objects.create_user(
            username=f'concurrent_student_{index}', password='test-pass', role='student',
            grade='七年级', class_num='1', student_number=str(index),
        )
        return ExecutionTask.objects.create(
            user=user, task_type=TASK_TYPE_RUN, code=f'print({index})',
            snapshot_hash=str(index) * 64, limits={},
            idempotency_key=str(uuid.uuid4()),
            expires_at=timezone.now() + timedelta(minutes=2),
        )

    def concurrent_claims(self):
        for index in range(2):
            RunnerNode.objects.create(
                runner_id=f'concurrent-runner-{index}',
                protocol_version='runner.v1',
                sandbox_image_digest='sha256:' + ('a' * 64),
                capacity=1,
                status='online',
                last_heartbeat_at=timezone.now(),
            )
        barrier = threading.Barrier(2)
        results = []
        errors = []

        def worker(runner_id):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                results.append(claim_task(runner_id=runner_id))
            except Exception as exc:  # surfaced below with its original repr
                errors.append(exc)
            finally:
                close_old_connections()

        threads = [
            threading.Thread(target=worker, args=(f'concurrent-runner-{index}',))
            for index in range(2)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertFalse(errors, repr(errors))
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        return results

    def test_concurrent_claims_never_return_same_task(self):
        self.make_task(1)
        self.make_task(2)

        results = self.concurrent_claims()

        task_ids = [result['task_id'] for result in results if result]
        self.assertEqual(len(task_ids), 2)
        self.assertEqual(len(set(task_ids)), 2)
        self.assertEqual(ExecutionTask.objects.filter(status=STATUS_RUNNING).count(), 2)

    def test_concurrent_claims_allow_only_one_running_task_per_student(self):
        user = CustomUser.objects.create_user(
            username='single_concurrent_student', password='test-pass', role='student',
            grade='七年级', class_num='1', student_number='single',
        )
        self.make_task(3, user=user)
        self.make_task(4, user=user)

        results = self.concurrent_claims()

        claimed = [result for result in results if result]
        self.assertEqual(len(claimed), 1)
        self.assertEqual(ExecutionTask.objects.filter(status=STATUS_RUNNING).count(), 1)
