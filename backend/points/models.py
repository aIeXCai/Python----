"""学生积分：余额快照 + append-only 流水。

设计要点（2026-11-24 定稿口径）：
- 打字练习：打多少次发多少次，按该场结算分全额发放，不封顶。
- 小测（信息科技 + AI 课）：同一场只认最高分，重复作答只在破纪录时补差。
- 流水只增不改，教师清零记一条等额负向流水，不删历史，便于追溯。
"""

from decimal import Decimal

from django.conf import settings
from django.db import models


ONE_DECIMAL = Decimal('0.1')
ZERO = Decimal('0.0')


class PointsReason(models.TextChoices):
    TYPING = 'typing_attempt', '打字练习'
    QUIZ_BEST = 'quiz_best', '小测最高分'
    HEX_REDRAW = 'hex_redraw', '刷新海克斯'
    TEACHER_ADJUST = 'teacher_adjust', '教师调整'
    TEACHER_RESET = 'teacher_reset', '教师清零'


class PointsAccount(models.Model):
    """余额快照。与流水同事务更新，避免每次展示都聚合流水。"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='points_account', verbose_name='学生',
    )
    balance = models.DecimalField('当前积分', max_digits=9, decimal_places=1, default=ZERO)
    # 称号「掉级但留荣誉」用：记录历史最高余额，跌破门槛后仍能显示「曾为 X」
    peak_balance = models.DecimalField(
        '历史最高积分', max_digits=9, decimal_places=1, default=ZERO,
    )
    earned_total = models.DecimalField('累计获得', max_digits=9, decimal_places=1, default=ZERO)
    spent_total = models.DecimalField('累计消耗', max_digits=9, decimal_places=1, default=ZERO)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '积分账户'
        verbose_name_plural = '积分账户'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(balance__gte=0),
                name='points_account_balance_non_negative',
            ),
        ]
        indexes = [
            # 班级风云榜按 (年级, 班级, 积分) 排序，走覆盖索引避免回表。
            models.Index(fields=['balance'], name='points_account_balance_idx'),
        ]

    def __str__(self):
        return f'{self.user_id}: {self.balance}'


class PointsLedger(models.Model):
    """积分流水。正数为获得，负数为消耗或清零。

    source_type + source_id + reason 三者唯一：同一场结算重复调用不会重复发放。
    source_group 用来聚合"同一场小测/同一次训练"，小测最高分补差依赖它求和。
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='points_ledger', verbose_name='学生',
    )
    delta = models.DecimalField('变动值', max_digits=7, decimal_places=1)
    balance_after = models.DecimalField('变动后余额', max_digits=9, decimal_places=1)
    reason = models.CharField('事由', max_length=24, choices=PointsReason.choices)
    source_type = models.CharField('来源类型', max_length=32, blank=True, default='')
    source_id = models.CharField('来源 ID', max_length=64, blank=True, default='')
    source_group = models.CharField('聚合键', max_length=64, blank=True, default='')
    note = models.CharField('备注', max_length=200, blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='points_adjustments', verbose_name='操作教师',
    )
    created_at = models.DateTimeField('时间', auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = '积分流水'
        verbose_name_plural = '积分流水'
        ordering = ['-id']
        constraints = [
            # 必须带上 user：不同学生对同一场结算各自发放，不能被彼此吞掉。
            models.UniqueConstraint(
                fields=['user', 'source_type', 'source_id', 'reason'],
                condition=~models.Q(source_type=''),
                name='points_ledger_source_unique',
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'created_at'], name='points_ledger_user_time'),
            models.Index(fields=['user', 'reason', 'source_group'], name='points_ledger_group_idx'),
        ]

    def __str__(self):
        return f'{self.user_id} {self.delta:+} ({self.reason})'
