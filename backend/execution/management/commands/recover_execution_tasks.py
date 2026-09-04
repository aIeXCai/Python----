from django.core.management.base import BaseCommand

from execution.queue import recover_expired_tasks


class Command(BaseCommand):
    help = '取消过期排队任务，并恢复或终止租约过期的执行任务。'

    def handle(self, *args, **options):
        result = recover_expired_tasks()
        self.stdout.write(
            self.style.SUCCESS(
                f"恢复完成：取消 {result['cancelled']}，"
                f"重新入队 {result['requeued']}，终止 {result['failed']}"
            )
        )
