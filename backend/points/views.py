"""积分接口：学生端看余额、班级风云榜、个人流水，教师端查改与批量清零。"""

from collections import Counter
from decimal import Decimal, InvalidOperation

from django.db.models import DecimalField, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import CustomUser
from users.permissions import IsStudent, IsTeacher
from users.scopes import TeacherScopeError, require_teacher_grade, scope_students
from users.views import no_store_response

from .models import ZERO, PointsAccount, PointsLedger, PointsReason
from .services import (
    PointsError,
    balance_for,
    class_rank,
    quantize,
    reset_points,
    teacher_adjust,
)
from .titles import ladder_payload, path_options, path_payload, tier_for, title_payload

MAX_ADJUST = Decimal('100000')

BALANCE_FIELD = DecimalField(max_digits=9, decimal_places=1)


def _balance_annotation():
    return Coalesce(
        Subquery(
            PointsAccount.objects.filter(user=OuterRef('pk')).values('balance')[:1],
            output_field=BALANCE_FIELD,
        ),
        Value(ZERO),
        output_field=BALANCE_FIELD,
    )


def _scope_error(exc):
    status_code = 400 if exc.code == 'invalid_grade' else 403
    return Response({'error': exc.message, 'code': exc.code}, status=status_code)


def _label(student, name_counts):
    """同班重名补学号，没有姓名回退学号（与打字海拔榜口径一致）。"""
    name = (student.get('display_name') or '').strip()
    number = (student.get('student_number') or '').strip()
    if not name:
        return f'{number} 号' if number else (student.get('username') or '')
    if number and name_counts.get(name, 0) > 1:
        return f'{name} {number}号'
    return name


class MyPointsView(APIView):
    """当前学生的积分，附带本班排名与规模，用于登录后顶部卡片。"""

    permission_classes = [IsStudent]

    def get(self, request):
        user = request.user
        account = PointsAccount.objects.filter(user=user).first()
        rank, balance = class_rank(user)
        class_size = CustomUser.objects.filter(
            role='student', is_active=True,
            grade=user.grade, class_num=user.class_num,
        ).count() if user.grade and user.class_num else 0

        # 累计发放（不含消费与清零的负向流水）：道号看的是"练过什么"，不是"还剩多少"
        totals = dict(
            PointsLedger.objects.filter(
                user=user, reason__in=(PointsReason.TYPING, PointsReason.QUIZ_BEST),
            ).values_list('reason').annotate(total=Sum('delta'))
        )
        typing_total = quantize(totals.get(PointsReason.TYPING))
        quiz_total = quantize(totals.get(PointsReason.QUIZ_BEST))

        title = title_payload(balance, account.peak_balance if account else None)
        title['path'] = path_payload(typing_total, quiz_total)

        return no_store_response({
            'balance': str(balance),
            'earned_total': str(quantize(account.earned_total)) if account else '0.0',
            'spent_total': str(quantize(account.spent_total)) if account else '0.0',
            'rank': rank,
            'class_size': class_size,
            'grade': user.grade or '',
            'class_num': user.class_num or '',
            'typing_total': str(typing_total),
            'quiz_total': str(quiz_total),
            'title': title,
            # 十阶天梯：点称号弹窗用，与本接口同一份积分快照，避免前端两次请求口径不一
            'ladder': ladder_payload(
                balance, account.peak_balance if account else None,
            ),
            'paths': path_options(),
        })


class PointsLeaderboardView(APIView):
    """班级风云榜：本班全部学生按积分降序，含打字/小测分项。"""

    permission_classes = [IsStudent]

    def get(self, request):
        user = request.user
        if not user.grade or not user.class_num:
            return no_store_response({
                'grade': user.grade or '', 'class_num': user.class_num or '',
                'entries': [], 'me': None,
            })

        rows = list(
            CustomUser.objects.filter(
                role='student', is_active=True,
                grade=user.grade, class_num=user.class_num,
            )
            .annotate(points=_balance_annotation())
            .values('id', 'display_name', 'username', 'student_number', 'points')
            .order_by('-points', 'id')
        )

        breakdown = {}
        if rows:
            ledger = PointsLedger.objects.filter(
                user_id__in=[row['id'] for row in rows],
                reason__in=(PointsReason.TYPING, PointsReason.QUIZ_BEST),
            ).values('user_id', 'reason').annotate(total=Sum('delta'))
            for item in ledger:
                bucket = breakdown.setdefault(item['user_id'], {})
                bucket[item['reason']] = quantize(item['total'])

        name_counts = Counter(
            (row['display_name'] or '').strip()
            for row in rows if (row['display_name'] or '').strip()
        )

        entries = []
        previous = None
        me = None
        for index, row in enumerate(rows, 1):
            points = quantize(row['points'])
            if points != previous:
                rank = index
            previous = points
            detail = breakdown.get(row['id'], {})
            tier = tier_for(points)
            typing_points = quantize(detail.get(PointsReason.TYPING))
            quiz_points = quantize(detail.get(PointsReason.QUIZ_BEST))
            entry = {
                'student_id': row['id'],
                'label': _label(row, name_counts),
                'points': str(points),
                'typing_points': str(typing_points),
                'quiz_points': str(quiz_points),
                'rank': rank,
                'self': row['id'] == user.pk,
                # 称号只给展示需要的字段，20 行不额外增加体积
                'title': {
                    'level': tier['level'],
                    'name': tier['name'],
                    'icon': tier['icon'],
                    'color': tier['color'],
                    'path': path_payload(typing_points, quiz_points),
                },
            }
            entries.append(entry)
            if entry['self']:
                me = entry

        return no_store_response({
            'grade': user.grade, 'class_num': user.class_num,
            'entries': entries, 'me': me,
        })


LEDGER_DEFAULT_LIMIT = 20
LEDGER_MAX_LIMIT = 100


class MyPointsLedgerView(APIView):
    """当前学生的积分明细（只读流水）。

    游标分页：`before` 传上一页最后一条的 id，避免 offset 在新增流水时错位。
    负数流水（消费/清零）照原样返回，由前端按正负渲染。
    """

    permission_classes = [IsStudent]

    def get(self, request):
        user = request.user
        try:
            limit = int(request.query_params.get('limit', LEDGER_DEFAULT_LIMIT))
        except (TypeError, ValueError):
            limit = LEDGER_DEFAULT_LIMIT
        limit = max(1, min(limit, LEDGER_MAX_LIMIT))

        queryset = PointsLedger.objects.filter(user=user)
        before = (request.query_params.get('before') or '').strip()
        if before.isdigit():
            queryset = queryset.filter(pk__lt=int(before))

        # 多取一条用来判断还有没有下一页，省一次 count 查询
        rows = list(queryset.order_by('-id')[: limit + 1])
        has_more = len(rows) > limit
        rows = rows[:limit]

        account = PointsAccount.objects.filter(user=user).first()
        entries = [
            {
                'id': row.pk,
                'delta': str(quantize(row.delta)),
                'balance_after': str(quantize(row.balance_after)),
                'reason': row.reason,
                'reason_label': row.get_reason_display(),
                'note': row.note or '',
                'created_at': timezone.localtime(row.created_at).isoformat(),
                'time': timezone.localtime(row.created_at).strftime('%m-%d %H:%M'),
            }
            for row in rows
        ]

        return no_store_response({
            'balance': str(quantize(account.balance)) if account else '0.0',
            'earned_total': str(quantize(account.earned_total)) if account else '0.0',
            'spent_total': str(quantize(account.spent_total)) if account else '0.0',
            'entries': entries,
            'has_more': has_more,
            'next_before': entries[-1]['id'] if has_more and entries else None,
        })


class AdminPointsStudentsView(APIView):
    """教师端学生积分列表，支持年级/班级/姓名学号检索。"""

    permission_classes = [IsTeacher]

    def get(self, request):
        try:
            grade = require_teacher_grade(request.user, request.query_params.get('grade'))
        except TeacherScopeError as exc:
            return _scope_error(exc)

        queryset = scope_students(
            CustomUser.objects.filter(role='student', is_active=True), request.user,
        )
        if grade:
            queryset = queryset.filter(grade=grade)
        class_num = (request.query_params.get('class_num') or '').strip()
        if class_num:
            queryset = queryset.filter(class_num=class_num)
        keyword = (request.query_params.get('q') or '').strip()
        if keyword:
            queryset = queryset.filter(
                Q(display_name__icontains=keyword)
                | Q(username__icontains=keyword)
                | Q(student_number__icontains=keyword)
            )

        students = list(
            queryset.annotate(points=_balance_annotation())
            .values('id', 'display_name', 'username', 'grade', 'class_num',
                    'student_number', 'points')
            .order_by('grade', 'class_num', 'id')[:300]
        )
        return Response({
            'grade': grade or '',
            'students': [
                {
                    'student_id': row['id'],
                    'name': (row['display_name'] or row['username'] or '').strip(),
                    'username': row['username'],
                    'grade': row['grade'],
                    'class_num': row['class_num'],
                    'student_number': row['student_number'] or '',
                    'points': str(quantize(row['points'])),
                    'title_name': tier_for(row['points'])['name'],
                }
                for row in students
            ],
        })


class AdminPointsAdjustView(APIView):
    """教师手动加减分。"""

    permission_classes = [IsTeacher]

    def post(self, request, student_id):
        student = scope_students(
            CustomUser.objects.filter(role='student', is_active=True), request.user,
        ).filter(pk=student_id).first()
        if student is None:
            return Response(
                {'error': '学生不在你的管理范围内', 'code': 'student_not_found'}, status=404,
            )
        try:
            delta = Decimal(str(request.data.get('delta', '')).strip())
        except (InvalidOperation, AttributeError, TypeError):
            return Response({'error': '请输入要调整的积分', 'code': 'invalid_delta'}, status=400)
        if delta == 0:
            return Response({'error': '调整值不能为 0', 'code': 'invalid_delta'}, status=400)
        if abs(delta) > MAX_ADJUST:
            return Response(
                {'error': f'单次调整不能超过 {MAX_ADJUST} 分', 'code': 'delta_too_large'}, status=400,
            )

        note = (request.data.get('note') or '').strip()
        try:
            ledger = teacher_adjust(request.user, student, delta, note=note)
        except PointsError as exc:
            return Response(
                {'error': exc.message, 'code': exc.code, **exc.extra}, status=exc.http_status,
            )
        return Response({
            'student_id': student.pk,
            'balance': str(balance_for(student)),
            'delta': str(quantize(delta)),
            'ledger_id': ledger.pk if ledger else None,
        })


class AdminPointsResetView(APIView):
    """按年级或按班级批量清零，写等额负向流水，可追溯。"""

    permission_classes = [IsTeacher]

    def post(self, request):
        requested = (request.data.get('grade') or '').strip()
        # 年级必须显式传入：留空不能回落到老师自己的管理年级，否则一次误点就清空整级。
        if not requested:
            return Response(
                {'error': '请指定要清零的年级', 'code': 'grade_required'}, status=400,
            )
        try:
            grade = require_teacher_grade(request.user, requested)
        except TeacherScopeError as exc:
            return _scope_error(exc)
        class_num = (request.data.get('class_num') or '').strip() or None
        note = (request.data.get('note') or '').strip()

        count, total = reset_points(
            request.user, grade=grade, class_num=class_num, note=note,
        )
        return Response({
            'grade': grade,
            'class_num': class_num or '',
            'cleared_count': count,
            'cleared_total': str(quantize(total)),
        })
