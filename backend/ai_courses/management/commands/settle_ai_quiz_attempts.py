from django.core.management.base import BaseCommand

from execution.queue import recover_expired_tasks

from ai_courses.quiz_settlement_services import settle_due_attempts


class Command(BaseCommand):
    help = '结算已超时或已具备终态评测结果的 AI 小测作答'

    def handle(self, *args, **options):
        recovered = recover_expired_tasks()
        settled = settle_due_attempts()
        self.stdout.write(self.style.SUCCESS(
            'AI 小测补偿完成：'
            f"取消过期排队 {recovered['cancelled']}，"
            f"重排租约过期 {recovered['requeued']}，"
            f"执行失败 {recovered['failed']}，"
            f"请求超时结算 {settled['expired_requested']}，"
            f"复查结算中 {settled['settling_checked']}"
        ))
