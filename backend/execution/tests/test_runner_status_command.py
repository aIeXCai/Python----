from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from execution.models import RunnerNode


@override_settings(RUNNER_NODE_STALE_SECONDS=30)
class RunnerStatusCommandTest(TestCase):
    def make_node(self, *, runner_id='runner-1', status='online', age_seconds=0):
        return RunnerNode.objects.create(
            runner_id=runner_id,
            protocol_version='runner.v1',
            sandbox_image_digest='local-python',
            capacity=2,
            active_slots=1,
            status=status,
            last_heartbeat_at=timezone.now() - timedelta(seconds=age_seconds),
        )

    def test_healthy_node_prints_capacity_and_succeeds(self):
        self.make_node()
        output = StringIO()
        call_command('runner_status', stdout=output)
        rendered = output.getvalue()
        self.assertIn('runner-1: 健康', rendered)
        self.assertIn('slots=1/2', rendered)
        self.assertIn('Local Runner 已就绪', rendered)

    def test_missing_stale_or_offline_nodes_fail(self):
        with self.assertRaisesMessage(CommandError, '无健康 Local Runner'):
            call_command('runner_status', stdout=StringIO(), stderr=StringIO())
        self.make_node(runner_id='stale', age_seconds=31)
        self.make_node(runner_id='offline', status='offline')
        with self.assertRaisesMessage(CommandError, '无健康 Local Runner'):
            call_command('runner_status', stdout=StringIO(), stderr=StringIO())

    def test_invalid_wait_is_rejected(self):
        with self.assertRaisesMessage(CommandError, '--wait'):
            call_command('runner_status', wait=301, stdout=StringIO(), stderr=StringIO())
