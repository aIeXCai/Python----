import time
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from execution.constants import RUNNER_STATUS_ONLINE
from execution.models import RunnerNode


class Command(BaseCommand):
    help = '显示 Local Runner 心跳状态，无健康节点时返回非零退出码。'

    def add_arguments(self, parser):
        parser.add_argument(
            '--wait', type=int, default=0, metavar='SECONDS',
            help='最多等待健康 Runner 出现的秒数。',
        )

    def _nodes(self):
        now = timezone.now()
        cutoff = now - timedelta(seconds=settings.RUNNER_NODE_STALE_SECONDS)
        nodes = list(RunnerNode.objects.order_by('runner_id'))
        healthy = [
            node for node in nodes
            if node.status == RUNNER_STATUS_ONLINE and node.last_heartbeat_at >= cutoff
        ]
        return now, nodes, healthy

    def handle(self, *args, **options):
        wait_seconds = options['wait']
        if wait_seconds < 0 or wait_seconds > 300:
            raise CommandError('--wait 必须在 0 到 300 之间')

        deadline = time.monotonic() + wait_seconds
        while True:
            now, nodes, healthy = self._nodes()
            if healthy or time.monotonic() >= deadline:
                break
            time.sleep(0.5)

        for node in nodes:
            age = max(0.0, (now - node.last_heartbeat_at).total_seconds())
            health = '健康' if node in healthy else '不可用'
            self.stdout.write(
                f'{node.runner_id}: {health}, status={node.status}, '
                f'slots={node.active_slots}/{node.capacity}, heartbeat_age={age:.1f}s'
            )
        if not healthy:
            raise CommandError(
                f'无健康 Local Runner（心跳时限 '
                f'{settings.RUNNER_NODE_STALE_SECONDS}s）'
            )
        self.stdout.write(self.style.SUCCESS(f'Local Runner 已就绪：{len(healthy)} 个健康节点'))
