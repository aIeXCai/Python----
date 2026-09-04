from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Q, Count, Avg, Max, Min, F, OuterRef, Subquery
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import Unit, Question, QuizSession, QuizSubmission
from .serializers import (
    UnitSerializer, QuestionSerializer,
    QuestionCreateSerializer, QuestionImportSerializer,
    QuizSessionSerializer, QuizSessionCreateSerializer,
    QuizSessionToggleSerializer, QuizSessionStatusSerializer,
    QuizAttemptResetSerializer,
)
from users.permissions import IsTeacher
from users.scopes import (
    TeacherScopeError, require_teacher_grade, scope_by_grade, scope_students,
)
from .quiz_services import QuizServiceError, close_session, reset_attempt, settle_expired_attempts
from .quiz_snapshot import SnapshotBuildError, build_quiz_snapshot


# ─── 教师权限mixin ────────────────────────────────────────────────────────────
def _scope_error(exc):
    return Response({'error': exc.message, 'code': exc.code}, status=403)


def _requested_grade(user, value=None):
    return require_teacher_grade(user, value)


class ClassListView(APIView):
    """GET /api/admin/info/classes/?grade=七年级 — 返回该年级已有学生班级。"""
    permission_classes = [IsTeacher]

    def get(self, request):
        try:
            grade = _requested_grade(request.user, request.query_params.get('grade'))
        except TeacherScopeError as exc:
            return _scope_error(exc)
        if not grade:
            return Response({'error': '请指定年级'}, status=400)
        User = get_user_model()
        values = User.objects.filter(
            role='student', grade=grade,
        ).exclude(class_num__isnull=True).exclude(class_num='').values_list(
            'class_num', flat=True,
        ).distinct()

        def natural_key(value):
            text = str(value)
            return (0, int(text)) if text.isdigit() else (1, text)

        classes = sorted({str(value) for value in values}, key=natural_key)
        return Response({'grade': grade, 'classes': classes})


# ─── Unit API ────────────────────────────────────────────────────────────────
class UnitListView(APIView):
    """GET /api/admin/info/units/?grade=七年级  列出大单元（嵌套sections）
       POST /api/admin/info/units/                新增大单元或小节"""
    permission_classes = [IsTeacher]

    def get(self, request):
        grade = request.query_params.get('grade')
        units = scope_by_grade(
            Unit.objects.filter(parent__isnull=True), request.user,
        ).order_by('grade', 'order')
        if grade:
            try:
                grade = _requested_grade(request.user, grade)
            except TeacherScopeError as exc:
                return _scope_error(exc)
            units = units.filter(grade=grade)
        serializer = UnitSerializer(units, many=True)
        return Response(serializer.data)

    def post(self, request):
        try:
            grade = _requested_grade(request.user, request.data.get('grade'))
        except TeacherScopeError as exc:
            return _scope_error(exc)
        if not grade:
            return Response({'error': '请指定年级'}, status=400)
        parent_id = request.data.get('parent')
        name = request.data.get('name')
        display_name = request.data.get('display_name', '')

        if not name:
            return Response({'error': 'name 不能为空'}, status=400)

        parent = None
        if parent_id:
            try:
                parent = scope_by_grade(
                    Unit.objects.filter(parent__isnull=True), request.user,
                ).get(pk=int(parent_id), grade=grade)
            except Unit.DoesNotExist:
                return Response({'error': '所属大单元不存在'}, status=400)

        if Unit.objects.filter(grade=grade, parent=parent, name=name).exists():
            return Response({'error': f'同年级下已存在同名单元 "{name}"'}, status=400)

        unit = Unit.objects.create(
            grade=grade, parent=parent, name=name,
            display_name=display_name or name,
            order=request.data.get('order', 0),
        )
        serializer = UnitSerializer(unit)
        return Response(serializer.data, status=201)


class UnitUpdateView(APIView):
    """PUT /api/admin/info/units/<id>/ 编辑单元"""
    permission_classes = [IsTeacher]

    def put(self, request, pk):
        try:
            unit = scope_by_grade(Unit.objects.all(), request.user).get(pk=pk)
        except Unit.DoesNotExist:
            return Response({'error': '单元不存在'}, status=404)

        unit.name = request.data.get('name', unit.name)
        unit.display_name = request.data.get('display_name', unit.display_name)
        try:
            unit.grade = _requested_grade(
                request.user, request.data.get('grade', unit.grade),
            )
        except TeacherScopeError as exc:
            return _scope_error(exc)
        unit.order = request.data.get('order', unit.order)
        parent_id = request.data.get('parent')
        if parent_id is not None:
            if parent_id == '' or parent_id is None:
                unit.parent = None
            else:
                try:
                    unit.parent = scope_by_grade(
                        Unit.objects.filter(parent__isnull=True), request.user,
                    ).get(pk=int(parent_id), grade=unit.grade)
                except Unit.DoesNotExist:
                    return Response({'error': '所属大单元不存在'}, status=400)
        unit.save()
        serializer = UnitSerializer(unit)
        return Response(serializer.data)


class UnitDeleteView(APIView):
    """DELETE /api/admin/info/units/<id>/delete/ 删除单元"""
    permission_classes = [IsTeacher]

    def delete(self, request, pk):
        try:
            unit = scope_by_grade(Unit.objects.all(), request.user).get(pk=pk)
        except Unit.DoesNotExist:
            return Response({'error': '单元不存在'}, status=404)
        unit.delete()
        return Response(status=204)


# ─── Question API ─────────────────────────────────────────────────────────────
class QuestionListView(APIView):
    """GET /api/admin/info/questions/ 题库列表（支持过滤）"""
    permission_classes = [IsTeacher]

    def get(self, request):
        qs = scope_by_grade(Question.objects.all(), request.user, 'unit__grade')

        # 按年级过滤
        grade = request.query_params.get('grade')
        if grade:
            try:
                grade = _requested_grade(request.user, grade)
            except TeacherScopeError as exc:
                return _scope_error(exc)
            qs = qs.filter(unit__grade=grade)

        # 按大单元过滤（通过 unit.parent.name 匹配）
        big_unit_name = request.query_params.get('big_unit_name')
        if big_unit_name:
            qs = qs.filter(unit__parent__name=big_unit_name)

        # 按小节过滤
        unit = request.query_params.get('unit')
        if unit:
            qs = qs.filter(unit__name=unit)

        # 按难度过滤
        difficulty = request.query_params.get('difficulty')
        if difficulty:
            qs = qs.filter(difficulty=difficulty)

        # 全文搜索
        q = request.query_params.get('q')
        if q:
            qs = qs.filter(Q(text__icontains=q) | Q(category__icontains=q))

        qs = qs.select_related('unit', 'unit__parent').order_by('id')
        serializer = QuestionSerializer(qs, many=True)
        return Response(serializer.data)


class QuestionCreateView(APIView):
    """POST /api/admin/info/questions/ 新增单题"""
    permission_classes = [IsTeacher]

    def post(self, request):
        serializer = QuestionCreateSerializer(
            data=request.data, context={'request': request},
        )
        if serializer.is_valid():
            question = serializer.save()
            return Response(QuestionSerializer(question).data, status=201)
        return Response(serializer.errors, status=400)


class QuestionUpdateView(APIView):
    """PUT /api/admin/info/questions/{id}/ 修改题目"""
    permission_classes = [IsTeacher]

    def put(self, request, pk):
        try:
            question = scope_by_grade(
                Question.objects.all(), request.user, 'unit__grade',
            ).get(pk=pk)
        except Question.DoesNotExist:
            return Response({'error': '题目不存在'}, status=404)

        serializer = QuestionCreateSerializer(
            question, data=request.data, context={'request': request},
        )
        if serializer.is_valid():
            question = serializer.save()
            return Response(QuestionSerializer(question).data)
        return Response(serializer.errors, status=400)


class QuestionDeleteView(APIView):
    """DELETE /api/admin/info/questions/{id}/ 删除题目"""
    permission_classes = [IsTeacher]

    def delete(self, request, pk):
        try:
            question = scope_by_grade(
                Question.objects.all(), request.user, 'unit__grade',
            ).get(pk=pk)
            question.delete()
            return Response({'detail': '删除成功'})
        except Question.DoesNotExist:
            return Response({'error': '题目不存在'}, status=404)


class QuestionImportView(APIView):
    """POST /api/admin/info/questions/import/ 批量导入 JSON"""
    permission_classes = [IsTeacher]

    def post(self, request):
        try:
            serializer = QuestionImportSerializer(
                data=request.data, context={'request': request},
            )
            if not serializer.is_valid():
                return Response(serializer.errors, status=400)

            result = serializer.save()
            unit_created = serializer.validated_data.get('unit_created', False)
            unit_obj = serializer.validated_data.get('unit')
            unit_name_str = unit_obj.name if unit_obj else ''

            msg = f"成功导入 {result['imported']} 题"
            if result['errors']:
                msg += f"，{len(result['errors'])} 题有错误"
            if unit_created:
                msg += f"（新建单元: {unit_name_str}）"

            return Response({
                'detail': msg,
                'imported': result['imported'],
                'unit_created': unit_created,
                'errors': result['errors'][:20]
            }, status=201)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({'error': str(e), 'type': type(e).__name__}, status=500)


# ─── QuizSession API ──────────────────────────────────────────────────────────


def _teacher_sessions(user):
    sessions = QuizSession.objects.filter(archived_at__isnull=True)
    if user.is_superuser:
        return sessions
    try:
        grade = require_teacher_grade(user)
    except TeacherScopeError:
        return sessions.none()
    return sessions.filter(
        Q(units__grade=grade) | Q(units__isnull=True, created_by=user),
    ).distinct()


def _teacher_session(user, pk):
    try:
        return _teacher_sessions(user).get(pk=pk)
    except QuizSession.DoesNotExist:
        return None


def _service_error(exc):
    return Response({'error': exc.message, 'code': exc.code, **exc.extra}, status=exc.http_status)


def _open_session(session, teacher, visible_grades=None, visible_classes=None):
    if session.status == QuizSession.STATUS_OPEN:
        return session
    if session.status not in (QuizSession.STATUS_DRAFT, QuizSession.STATUS_CLOSED):
        raise QuizServiceError('invalid_quiz_transition', '小测当前不能开放', 409)
    is_first_publish = session.status == QuizSession.STATUS_DRAFT
    grades = (
        visible_grades if is_first_publish and visible_grades is not None
        else session.visible_grades
    )
    if not teacher.is_superuser:
        try:
            managed = require_teacher_grade(teacher)
        except TeacherScopeError as exc:
            raise QuizServiceError(exc.code, exc.message, 403) from exc
        grades = [managed] if not grades else grades
        if any(grade != managed for grade in grades):
            raise QuizServiceError('teacher_grade_forbidden', '不能发布到管理范围外的年级', 403)
    session.visible_grades = grades or []
    if is_first_publish and visible_classes is not None:
        session.visible_classes = visible_classes
    try:
        build_quiz_snapshot(session)
    except SnapshotBuildError as exc:
        raise QuizServiceError('quiz_pool_insufficient', str(exc), 409) from exc
    from django.utils import timezone
    session.status = QuizSession.STATUS_OPEN
    session.opened_at = timezone.now()
    session.closed_at = None
    session.save(update_fields=[
        'status', 'opened_at', 'closed_at', 'visible_grades', 'visible_classes', 'updated_at',
    ])
    return session

class QuizSessionListView(APIView):
    """GET /api/admin/info/sessions/ 小测列表"""
    permission_classes = [IsTeacher]

    def get(self, request):
        sessions = _teacher_sessions(request.user).prefetch_related('units').order_by('-created_at')
        serializer = QuizSessionSerializer(sessions, many=True)
        return Response(serializer.data)


class QuizSessionCreateView(APIView):
    """POST /api/admin/info/sessions/create/ 创建小测"""
    permission_classes = [IsTeacher]

    def post(self, request):
        try:
            require_teacher_grade(request.user)
        except TeacherScopeError as exc:
            return _scope_error(exc)
        serializer = QuizSessionCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            session = serializer.save()
            if request.data.get('is_visible') is True:
                try:
                    session = _open_session(session, request.user, session.visible_grades)
                except QuizServiceError as exc:
                    session.delete()
                    return _service_error(exc)
            return Response(QuizSessionSerializer(session).data, status=201)
        return Response(serializer.errors, status=400)


class QuizSessionUpdateView(APIView):
    """PUT /api/admin/info/sessions/{id}/ 修改小测"""
    permission_classes = [IsTeacher]

    def put(self, request, pk):
        session = _teacher_session(request.user, pk)
        if not session:
            return Response({'error': '小测不存在'}, status=404)

        serializer = QuizSessionCreateSerializer(session, data=request.data, context={'request': request})
        if serializer.is_valid():
            original_status = session.status
            try:
                with transaction.atomic():
                    session = serializer.save()
                    if original_status != QuizSession.STATUS_DRAFT:
                        build_quiz_snapshot(session)
                    if request.data.get('is_visible') is True:
                        session = _open_session(session, request.user, session.visible_grades)
            except SnapshotBuildError as exc:
                return Response(
                    {'error': str(exc), 'code': 'quiz_pool_insufficient'}, status=409,
                )
            except QuizServiceError as exc:
                return _service_error(exc)
            return Response(QuizSessionSerializer(session).data)
        return Response(serializer.errors, status=400)


class QuizSessionDeleteView(APIView):
    """DELETE /api/admin/info/sessions/{id}/delete/ 删除小测"""
    permission_classes = [IsTeacher]

    def delete(self, request, pk):
        session = _teacher_session(request.user, pk)
        if not session:
            return Response({'error': '小测不存在'}, status=404)
        if not session.quizsubmission_set.exists():
            session.delete()
            return Response({'detail': '删除成功', 'deletion_mode': 'permanent'})

        with transaction.atomic():
            if session.status == QuizSession.STATUS_OPEN:
                session = close_session(request.user, session)
            session.archived_at = timezone.now()
            session.save(update_fields=['archived_at', 'updated_at'])
        return Response({
            'detail': '小测已删除，历史成绩已安全保留',
            'deletion_mode': 'archived',
        })


class QuizSessionToggleView(APIView):
    """PATCH /api/admin/info/sessions/{id}/toggle/ 切换可见性"""
    permission_classes = [IsTeacher]

    def patch(self, request, pk):
        session = _teacher_session(request.user, pk)
        if not session:
            return Response({'error': '小测不存在'}, status=404)

        serializer = QuizSessionToggleSerializer(data=request.data)
        if serializer.is_valid():
            try:
                if serializer.validated_data['is_visible']:
                    session = _open_session(
                        session, request.user,
                        serializer.validated_data.get('visible_grades'),
                        serializer.validated_data.get('visible_classes'),
                    )
                else:
                    session = close_session(request.user, session)
                return Response(QuizSessionSerializer(session).data)
            except QuizServiceError as exc:
                return _service_error(exc)
        return Response(serializer.errors, status=400)


class QuizSessionStatusView(APIView):
    permission_classes = [IsTeacher]

    def patch(self, request, pk):
        session = _teacher_session(request.user, pk)
        if not session:
            return Response({'error': '小测不存在'}, status=404)
        serializer = QuizSessionStatusSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        try:
            if serializer.validated_data['status'] == QuizSession.STATUS_OPEN:
                session = _open_session(
                    session, request.user,
                    serializer.validated_data.get('visible_grades'),
                    serializer.validated_data.get('visible_classes'),
                )
            else:
                session = close_session(request.user, session)
            return Response(QuizSessionSerializer(session).data)
        except QuizServiceError as exc:
            return _service_error(exc)


class QuizAttemptResetView(APIView):
    permission_classes = [IsTeacher]

    def post(self, request, pk, student_id):
        session = _teacher_session(request.user, pk)
        if not session:
            return Response({'error': '小测不存在'}, status=404)
        serializer = QuizAttemptResetSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        User = get_user_model()
        student = scope_students(
            User.objects.filter(role='student'), request.user,
        ).filter(pk=student_id).first()
        if student is None:
            return Response({'error': '学生不存在'}, status=404)
        try:
            attempt = reset_attempt(
                request.user, session, student, serializer.validated_data['reason'],
            )
            return Response({
                'attempt_id': attempt.pk,
                'student_id': student.pk,
                'reset_at': attempt.reset_at,
                'can_start_again': True,
            })
        except QuizServiceError as exc:
            return _service_error(exc)


# ─── 成绩统计 API ─────────────────────────────────────────────────────────────


def _teacher_results(user):
    session_ids = _teacher_sessions(user).values_list('id', flat=True)
    settle_expired_attempts(session_ids=session_ids)
    latest_settled_id = QuizSubmission.objects.filter(
        user_id=OuterRef('user_id'),
        session_id=OuterRef('session_id'),
        status__in=(QuizSubmission.STATUS_SUBMITTED, QuizSubmission.STATUS_TIMED_OUT),
    ).order_by('-attempt_no', '-id').values('id')[:1]
    results = QuizSubmission.objects.filter(
        session__in=_teacher_sessions(user),
        status__in=(QuizSubmission.STATUS_SUBMITTED, QuizSubmission.STATUS_TIMED_OUT),
    ).annotate(latest_settled_id=Subquery(latest_settled_id)).filter(id=F('latest_settled_id'))
    return scope_by_grade(results, user)


def _grade_forbidden(user, grade):
    try:
        require_teacher_grade(user, grade)
        return False
    except TeacherScopeError:
        return True

class QuizStatsOverviewView(APIView):
    """GET /api/admin/info/stats/overview/ 全局概览，支持 grade/class_num 筛选"""
    permission_classes = [IsTeacher]

    def get(self, request):
        grade = request.query_params.get('grade')
        class_num = request.query_params.get('class_num')
        if _grade_forbidden(request.user, grade):
            return Response({'error': '不能查看管理范围外的年级'}, status=403)

        subs = _teacher_results(request.user)
        if grade:
            subs = subs.filter(grade=grade)
        if class_num:
            subs = subs.filter(class_num_snapshot=class_num)

        total_sessions = _teacher_sessions(request.user).count()
        total_submissions = subs.count()
        avg_score = subs.aggregate(avg=Avg('score'))['avg'] or 0
        scores = list(subs.values_list('score', flat=True))
        p90 = sorted(scores)[int(len(scores) * 0.9)] if len(scores) >= 10 else max(scores, default=0)
        p50 = sorted(scores)[int(len(scores) * 0.5)] if len(scores) >= 2 else max(scores, default=0)

        # 分数段分布
        bins = {'0-60': 0, '60-80': 0, '80-100': 0}
        for s in scores:
            if s < 60:
                bins['0-60'] += 1
            elif s < 80:
                bins['60-80'] += 1
            else:
                bins['80-100'] += 1

        # 按年级统计（如果有筛选则基于筛选后的数据）
        grade_stats = subs.values('grade').annotate(
            count=Count('id'),
            avg_score=Avg('score')
        ).order_by('-count')

        return Response({
            'total_sessions': total_sessions,
            'total_submissions': total_submissions,
            'avg_score': round(avg_score, 1),
            'p50_score': round(p50, 1),
            'p90_score': round(p90, 1),
            'score_distribution': bins,
            'by_grade': list(grade_stats),
        })


class QuizStatsSessionView(APIView):
    """GET /api/admin/info/stats/sessions/ 按小测统计"""
    permission_classes = [IsTeacher]

    def get(self, request):
        grade = request.query_params.get('grade')
        class_num = request.query_params.get('class_num')
        if _grade_forbidden(request.user, grade):
            return Response({'error': '不能查看管理范围外的年级'}, status=403)

        sessions = _teacher_sessions(request.user).order_by('-created_at')
        result = []
        for s in sessions:
            subs = _teacher_results(request.user).filter(session=s)
            if grade:
                subs = subs.filter(grade=grade)
            if class_num:
                subs = subs.filter(class_num_snapshot=class_num)
            total = subs.count()
            result.append({
                'session_id': s.id,
                'title': s.title,
                'grade': grade or None,
                'total_submissions': total,
                'avg_score': round(subs.aggregate(avg=Avg('score'))['avg'], 1) if total > 0 else None,
                'max_score': subs.aggregate(max=Max('score'))['max'],
                'min_score': subs.aggregate(min=Min('score'))['min'],
            })

        return Response(result)


class QuizStatsSessionDetailView(APIView):
    """GET /api/admin/info/stats/sessions/<id>/ 某小测详细统计"""
    permission_classes = [IsTeacher]

    def get(self, request, pk):
        session = _teacher_session(request.user, pk)
        if not session:
            return Response({'error': '小测不存在'}, status=404)

        subs = _teacher_results(request.user).filter(session=session)
        all_current = scope_by_grade(
            session.quizsubmission_set.filter(current_marker=True), request.user,
        )
        status_counts = {
            'in_progress': all_current.filter(status=QuizSubmission.STATUS_IN_PROGRESS).count(),
            'submitted': all_current.filter(status=QuizSubmission.STATUS_SUBMITTED).count(),
            'timed_out': all_current.filter(status=QuizSubmission.STATUS_TIMED_OUT).count(),
            'reset': scope_by_grade(
                session.quizsubmission_set.filter(status=QuizSubmission.STATUS_RESET),
                request.user,
            ).count(),
        }
        total = subs.count()
        if total == 0:
            return Response({
                'session_id': session.id, 'title': session.title,
                'total_submissions': 0,
                'avg_score': None, 'max_score': None, 'min_score': None,
                'by_grade': [], 'question_stats': [], 'status_counts': status_counts,
            })

        # 按年级
        by_grade = subs.values('grade').annotate(
            count=Count('id'),
            avg_score=Avg('score')
        ).order_by('grade')

        # 按快照统计，未答题也进入分母；题库后续修改不改变历史结果。
        question_data = {}
        for sub in subs:
            if sub.snapshot_version != 1 or not sub.snapshot_json:
                continue
            answers = sub.answers
            for item in sub.snapshot_json.get('questions', []):
                key = item.get('source_question_id') or item.get('item_id')
                entry = question_data.setdefault(key, {
                    'question_id': key,
                    'text': item.get('text', '')[:60],
                    'difficulty': item.get('difficulty', ''),
                    'category': item.get('category', ''),
                    'attempted': 0,
                    'correct': 0,
                })
                entry['attempted'] += 1
                if answers.get(item.get('item_id')) == item.get('correct_option'):
                    entry['correct'] += 1

        question_stats = []
        for entry in question_data.values():
            attempted = entry['attempted']
            entry['correct_rate'] = round(entry['correct'] / attempted * 100, 1) if attempted else 0
            question_stats.append(entry)

        question_stats.sort(key=lambda x: x['correct_rate'])

        return Response({
            'session_id': session.id,
            'title': session.title,
            'total_submissions': total,
            'avg_score': round(subs.aggregate(avg=Avg('score'))['avg'], 1),
            'max_score': subs.aggregate(max=Max('score'))['max'],
            'min_score': subs.aggregate(min=Min('score'))['min'],
            'by_grade': list(by_grade),
            'question_stats': question_stats,
            'status_counts': status_counts,
        })


class QuizStatsGradeView(APIView):
    """GET /api/admin/info/stats/grade/<grade>/ 按年级详细统计"""
    permission_classes = [IsTeacher]

    def get(self, request, grade):
        if _grade_forbidden(request.user, grade):
            return Response({'error': '不能查看管理范围外的年级'}, status=403)
        subs = _teacher_results(request.user).filter(grade=grade)
        if not subs.exists():
            return Response({'error': '该年级暂无数据'}, status=404)

        by_session = subs.values('session__title').annotate(
            count=Count('id'),
            avg_score=Avg('score')
        )

        return Response({
            'grade': grade,
            'total_submissions': subs.count(),
            'avg_score': round(subs.aggregate(avg=Avg('score'))['avg'], 1),
            'by_session': list(by_session),
        })


class QuizStatsSubmissionsView(APIView):
    """GET /api/admin/info/stats/submissions/ 学生个体成绩（满分矩阵）
    查询参数: grade, class_num, session_id
    """
    permission_classes = [IsTeacher]

    def get(self, request):
        grade = request.query_params.get('grade')
        class_num = request.query_params.get('class_num')
        session_id = request.query_params.get('session_id')
        if _grade_forbidden(request.user, grade):
            return Response({'error': '不能查看管理范围外的年级'}, status=403)

        subs = _teacher_results(request.user).select_related('user', 'session').order_by(
            'grade', 'class_num_snapshot', 'student_number_snapshot',
        )

        if grade:
            subs = subs.filter(grade=grade)
        if class_num:
            subs = subs.filter(class_num_snapshot=class_num)
        if session_id:
            subs = subs.filter(session_id=int(session_id))

        if not subs.exists():
            return Response({'students': [], 'sessions': []})

        # 收集所有涉及的 session
        session_ids = sorted(set(subs.values_list('session_id', flat=True)))
        sessions = _teacher_sessions(request.user).filter(id__in=session_ids).order_by('created_at')
        session_titles = {s.id: s.title for s in sessions}

        # 按学生聚合
        from collections import defaultdict
        student_map = defaultdict(lambda: {'scores': {}})
        for sub in subs:
            key = (sub.user_id, sub.user.display_name, sub.grade, sub.class_num_snapshot, sub.student_number_snapshot)
            student_map[key]['display_name'] = sub.user.display_name
            student_map[key]['grade'] = sub.grade
            student_map[key]['class_num'] = sub.class_num_snapshot
            student_map[key]['student_number'] = sub.student_number_snapshot
            student_map[key]['scores'][sub.session_id] = sub.score

        rows = []
        for (uid, dname, grade, cls, snum), data in sorted(student_map.items()):
            row = {
                'user_id': uid,
                'display_name': dname,
                'grade': grade,
                'class_num': cls,
                'student_number': snum,
                'scores': [data['scores'].get(sid) for sid in session_ids],
            }
            # 计算该学生平均
            scores = [s for s in row['scores'] if s is not None]
            row['avg_score'] = round(sum(scores) / len(scores), 1) if scores else None
            rows.append(row)

        return Response({
            'sessions': [{'id': sid, 'title': session_titles[sid]} for sid in session_ids],
            'students': rows,
        })
