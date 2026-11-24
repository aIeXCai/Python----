"""积分服务层。

三条业务规则（2026-11-24 定稿）：
1. 打字练习：每完成一场就发放，打多少次发多少次，**不封顶**；
   但单价按 POINTS_TYPING_WEIGHT（默认 0.6）折算——打字可无限重复，
   原分 1:1 会让「多刷打字」压过小测，见 `typing_weight()`。
2. 小测（信息科技 + AI 课）：同一场只认最高分。重复作答只有在破纪录时补差额，
   例如 80 → 90 只补 10，之后再考 85 不再发放。
3. 教师清零：写一条等额负向流水，不删除历史。

并发控制：所有写操作先对 CustomUser 行加锁，同一学生的结算与扣减因此串行化；
配合 `points_ledger_source_unique` 唯一约束，重复调用（双击、重试）不会重复发放。
"""

import logging
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import transaction
from django.db.models import Max, Sum

from users.models import CustomUser

from .models import ONE_DECIMAL, ZERO, PointsAccount, PointsLedger, PointsReason

logger = logging.getLogger(__name__)


class PointsError(Exception):
    """积分业务错误，由视图层转换成统一响应。"""

    def __init__(self, code, message, http_status=400, **extra):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.extra = extra


def quantize(value):
    """统一结算到 0.1 精度，与成绩的显示精度一致。"""
    if value is None:
        return ZERO
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(ONE_DECIMAL, rounding=ROUND_HALF_UP)


def _start_at():
    """POINTS_START_AT 允许写日期或带时区的 ISO 时间，统一解析成 aware datetime。"""
    from datetime import datetime

    from django.utils import timezone
    from django.utils.dateparse import parse_date, parse_datetime

    raw = getattr(settings, 'POINTS_START_AT', '')
    if not raw:
        return None
    if isinstance(raw, datetime):
        value = raw
    else:
        value = parse_datetime(str(raw))
        if value is None:
            day = parse_date(str(raw))
            if day is None:
                logger.warning('POINTS_START_AT 无法解析，已按不设限处理: %s', raw)
                return None
            value = datetime.combine(day, datetime.min.time())
    if timezone.is_naive(value):
        value = timezone.make_aware(value)
    return value


def _award_allowed(settled_at):
    """上线时间护栏：早于 POINTS_START_AT 的成绩不发积分（防止历史数据补发）。"""
    start = _start_at()
    if start and settled_at is not None and settled_at < start:
        return False
    return True


def typing_weight():
    """打字积分折算系数（默认 0.6），读 settings 便于按班情调，不写死。

    存在的原因：打字可以无限重复，小测一场封顶 100 分。若按原分 1:1 发放，
    「每节课 2 次打字 + 1 次小测」的标准节奏必然是小测的 2 倍，道号「智识」
    永远出不来，双修也无从谈起。折算后标准节奏为 120 : 100，结构才可比。
    """
    raw = getattr(settings, 'POINTS_TYPING_WEIGHT', '0.6')
    try:
        weight = Decimal(str(raw))
    except (ArithmeticError, TypeError, ValueError):
        logger.warning('POINTS_TYPING_WEIGHT 无法解析，按 0.6 处理: %r', raw)
        return Decimal('0.6')
    if weight <= 0 or weight > 1:
        logger.warning('POINTS_TYPING_WEIGHT 超出 (0, 1]，按 0.6 处理: %r', raw)
        return Decimal('0.6')
    return weight


def typing_points_for(score):
    """打字成绩 → 实际发放积分。结算与演示数据都走这里，避免两套口径。"""
    return quantize(max(ZERO, quantize(score)) * typing_weight())


def _lock_user(user):
    """锁定学生行；同一学生的所有积分写操作由此串行化。

    注意锁顺序：小测交卷路径是「作答行 → 学生行」，开始作答路径是「学生行 → 作答行」，
    理论上存在相反顺序。当前用 SQLite（写串行）无影响；迁移 MySQL 后若出现死锁日志，
    把三个结算钩子改成 transaction.on_commit 里结算即可。
    """
    user_id = user.pk if hasattr(user, 'pk') else user
    return CustomUser.objects.select_for_update().get(pk=user_id)


def _locked_account(user):
    account, _ = PointsAccount.objects.get_or_create(user=user)
    return PointsAccount.objects.select_for_update().get(pk=account.pk)


def _apply_locked(user, delta, *, reason, source_type='', source_id='',
                  source_group='', note='', created_by=None):
    """在已持有用户锁的事务内落一笔流水。返回新建流水，金额为 0 时返回 None。

    调用方必须已经处在 transaction.atomic() 中并持有该用户的行锁。
    """
    delta = quantize(delta)
    if delta == 0:
        return None

    account = _locked_account(user)
    balance = quantize(account.balance) + delta
    if balance < 0:
        raise PointsError(
            'insufficient_points',
            f'积分不足，当前 {quantize(account.balance)}，本次需要 {abs(delta)}',
            409,
            balance=str(quantize(account.balance)),
            required=str(abs(delta)),
        )

    account.balance = balance
    # 称号用：历史最高只升不降，清零或扣分都不会抹掉「曾为天骄」的痕迹
    if balance > quantize(account.peak_balance):
        account.peak_balance = balance
    if delta > 0:
        account.earned_total = quantize(account.earned_total) + delta
    else:
        account.spent_total = quantize(account.spent_total) - delta
    account.save(update_fields=[
        'balance', 'peak_balance', 'earned_total', 'spent_total', 'updated_at',
    ])

    return PointsLedger.objects.create(
        user=user,
        delta=delta,
        balance_after=balance,
        reason=reason,
        source_type=source_type,
        source_id=source_id,
        source_group=source_group,
        note=note[:200],
        created_by=created_by,
    )


def _existing(user, source_type, source_id, reason):
    if not source_type:
        return None
    return PointsLedger.objects.filter(
        user=user, source_type=source_type, source_id=str(source_id), reason=reason,
    ).first()


def award_points(user, amount, *, reason, source_type='', source_id='',
                 source_group='', note='', created_by=None):
    """发放积分（幂等：source_type + source_id + reason 相同只发一次）。"""
    amount = quantize(amount)
    if amount <= 0:
        return None
    with transaction.atomic():
        locked = _lock_user(user)
        existing = _existing(locked, source_type, source_id, reason)
        if existing:
            return existing
        return _apply_locked(
            locked, amount, reason=reason, source_type=source_type,
            source_id=str(source_id), source_group=source_group,
            note=note, created_by=created_by,
        )


def spend_points(user, amount, *, reason=PointsReason.HEX_REDRAW,
                 source_type='', source_id='', source_group='', note=''):
    """消耗积分，余额不足时抛 PointsError。"""
    amount = quantize(amount)
    if amount <= 0:
        raise PointsError('invalid_amount', '消耗的积分必须大于 0')
    with transaction.atomic():
        locked = _lock_user(user)
        existing = _existing(locked, source_type, source_id, reason)
        if existing:
            return existing
        return _apply_locked(
            locked, -amount, reason=reason, source_type=source_type,
            source_id=str(source_id), source_group=source_group, note=note,
        )


def teacher_adjust(actor, student, delta, *, note=''):
    """教师手动加减分。delta 可为负，扣到负数会被拒绝。"""
    delta = quantize(delta)
    if delta == 0:
        raise PointsError('invalid_amount', '调整值不能为 0')
    with transaction.atomic():
        locked = _lock_user(student)
        return _apply_locked(
            locked, delta, reason=PointsReason.TEACHER_ADJUST,
            note=note or f'{actor.username} 手动调整', created_by=actor,
        )


def reset_points(actor, *, grade, class_num=None, note=''):
    """按班或按年级清零，返回 (人数, 清零总额)。

    逐人写等额负向流水，历史可查；余额为 0 的学生跳过。
    """
    students = CustomUser.objects.filter(
        role='student', is_active=True, grade=grade,
    )
    if class_num:
        students = students.filter(class_num=class_num)
    student_ids = list(students.values_list('id', flat=True))
    if not student_ids:
        return 0, ZERO

    target = (
        PointsAccount.objects
        .filter(user_id__in=student_ids, balance__gt=0)
        .values_list('user_id', flat=True)
    )
    target_ids = list(target)
    if not target_ids:
        return 0, ZERO

    scope_label = f'{grade}{class_num or ""}'
    cleared_total = ZERO
    cleared_count = 0
    for user_id in target_ids:
        with transaction.atomic():
            locked = _lock_user(user_id)
            account = _locked_account(locked)
            balance = quantize(account.balance)
            if balance <= 0:
                continue
            _apply_locked(
                locked, -balance, reason=PointsReason.TEACHER_RESET,
                note=note or f'{scope_label} 批量清零，操作人 {actor.username}',
                created_by=actor,
            )
            cleared_total += balance
            cleared_count += 1
    return cleared_count, cleared_total


def balance_for(user):
    account = PointsAccount.objects.filter(user=user).first()
    return quantize(account.balance) if account else ZERO


def class_rank(user):
    """本班排名（并列同名次）。没有账户的学生记 0 分。"""
    balance = balance_for(user)
    if not user.grade or not user.class_num:
        return 1, balance
    ahead = PointsAccount.objects.filter(
        user__role='student',
        user__is_active=True,
        user__grade=user.grade,
        user__class_num=user.class_num,
        balance__gt=balance,
    ).count()
    return ahead + 1, balance


# ─── 结算入口：由打字/小测的结算流程调用 ─────────────────────────────────────


def settle_typing(attempt, score, *, settled_at=None):
    """打字练习结算：每场都发（不封顶、不去重），金额按折算系数打折。"""
    from django.utils import timezone

    settled_at = settled_at or timezone.now()
    if not _award_allowed(settled_at):
        return None
    raw = quantize(score)
    amount = typing_points_for(raw)
    if amount <= 0:
        return None
    return award_points(
        attempt.student_id, amount,
        reason=PointsReason.TYPING,
        source_type='typing_attempt',
        source_id=str(attempt.pk),
        source_group=f'typing_activity:{attempt.activity_id}',
        note=f'打字练习 {raw} 分 × {typing_weight()}'[:200],
    )


def _award_session_best(user_id, best, *, source_type, source_id, group, activity):
    """小测最高分补差：只在本次结算刷新纪录时发放差额。"""
    best = quantize(best)
    if best <= 0:
        return None
    with transaction.atomic():
        locked = _lock_user(user_id)
        existing = _existing(locked, source_type, source_id, PointsReason.QUIZ_BEST)
        if existing:
            return existing
        awarded = PointsLedger.objects.filter(
            user_id=locked.pk,
            reason=PointsReason.QUIZ_BEST,
            source_group=group,
        ).aggregate(total=Sum('delta'))['total']
        awarded = quantize(awarded)
        if best <= awarded:
            return None
        return _apply_locked(
            locked, best - awarded,
            reason=PointsReason.QUIZ_BEST,
            source_type=source_type,
            source_id=str(source_id),
            source_group=group,
            note=activity,
        )


def settle_info_quiz(attempt, *, settled_at=None):
    """信息科技小测：同场只认最高分，破纪录才补差。"""
    from info_tech.models import QuizSubmission

    if attempt.score is None:
        return None
    settled_at = settled_at or attempt.submitted_at
    if not _award_allowed(settled_at):
        return None
    best = QuizSubmission.objects.filter(
        user_id=attempt.user_id,
        session_id=attempt.session_id,
        status__in=(QuizSubmission.STATUS_SUBMITTED, QuizSubmission.STATUS_TIMED_OUT),
        score__isnull=False,
    ).aggregate(value=Max('score'))['value']
    return _award_session_best(
        attempt.user_id, best,
        source_type='info_quiz_attempt',
        source_id=str(attempt.pk),
        group=f'info_session:{attempt.session_id}',
        activity=f'信息科技小测 · {attempt.session.title}',
    )


def settle_ai_quiz(attempt, *, settled_at=None):
    """AI 课小测：同场只认最高分。"""
    from ai_courses.models import AIQuizAttempt

    if attempt.total_score is None:
        return None
    settled_at = settled_at or attempt.settled_at
    if not _award_allowed(settled_at):
        return None
    best = AIQuizAttempt.objects.filter(
        user_id=attempt.user_id,
        session_id=attempt.session_id,
        total_score__isnull=False,
        settled_at__isnull=False,
    ).exclude(status=AIQuizAttempt.STATUS_RESET).aggregate(value=Max('total_score'))['value']
    return _award_session_best(
        attempt.user_id, best,
        source_type='ai_quiz_attempt',
        source_id=str(attempt.pk),
        group=f'ai_session:{attempt.session_id}',
        activity=f'人工智能小测 · {attempt.session.title}',
    )


def safe_settle(func, *args, **kwargs):
    """结算钩子兜底：积分出错不能让学生的交卷/提交一起失败。"""
    try:
        return func(*args, **kwargs)
    except Exception:  # pragma: no cover - 记录后由运维按流水补齐
        logger.exception('积分结算失败: %s', getattr(func, '__name__', func))
        return None
