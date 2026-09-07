import datetime
from django.conf import settings
from django.db.models import Max, Avg, Count, OuterRef, Subquery, Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import Problem, ProblemManagementAudit, Submission
from .serializers import (
    ProblemListSerializer,
    ProblemDetailSerializer,
    SubmissionCreateSerializer,
    SubmissionHistorySerializer,
    ScoreSerializer,
    StudentStatsSerializer,
    AdminStatsSerializer,
    AdminProblemListSerializer,
    AdminProblemDetailSerializer,
    ProblemContentUpdateSerializer,
    TeacherProblemAudienceUpdateSerializer,
    AdminProblemAudienceUpdateSerializer,
    ProblemVersionSerializer,
)
from execution.serializers import CodeRunCreateSerializer, public_task_data
from execution.services import ExecutionRequestError, enqueue_grade, enqueue_run
from execution.snapshots import InvalidTestSnapshot
from users.permissions import IsStudent, IsTeacher
from users.grade_levels import normalize_grade
from users.scopes import (
    TeacherScopeError,
    is_platform_admin,
    require_teacher_grade,
    scope_students,
)
from users.models import CustomUser
from .problem_management import (
    ProblemManagementError,
    archive_problem,
    edit_problem_content,
    publication_data,
    restore_problem,
    update_problem_audience,
)
from .problem_scopes import get_visible_problem_or_404, visible_problems_for_student


def _code_execution_unavailable_response():
    """Fail closed instead of falling back to local execution."""
    if not getattr(settings, 'CODE_EXECUTION_ENABLED', False):
        return Response(
            {'error': '代码执行服务暂不可用，请稍后重试'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return None


def _execution_error_response(exc):
    return Response(
        {'error': exc.message, 'code': exc.code},
        status=exc.status_code,
    )


def _source_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return (forwarded.split(',', 1)[0].strip() if forwarded else request.META.get('REMOTE_ADDR')) or None


def _management_error_response(exc):
    data = {'error': exc.message, 'code': exc.code}
    if exc.current_version is not None:
        data['management_version'] = exc.current_version
    return Response(data, status=exc.status_code)


# ============================================================
# 学生端 API
# ============================================================

class ProblemListView(APIView):
    """
    GET /api/ai/problems/?course=ai
    获取题目列表（学生用）
    """
    permission_classes = [IsStudent]

    def get(self, request):
        course = request.query_params.get('course', 'ai')
        problems = visible_problems_for_student(
            Problem.objects.filter(course=course), request.user,
        )
        serializer = ProblemListSerializer(problems, many=True)
        return Response(serializer.data)


class ProblemDetailView(APIView):
    """
    GET /api/ai/problems/<problem_id>/
    获取题目详情（含测试点）
    """
    permission_classes = [IsStudent]

    def get(self, request, problem_id):
        course = request.query_params.get('course', 'ai')
        problem = get_visible_problem_or_404(
            request.user, problem_id, course=course,
        )
        serializer = ProblemDetailSerializer(problem)
        return Response(serializer.data)


class SubmissionView(APIView):
    """
    POST /api/ai/submissions/
    学生提交代码
    """
    permission_classes = [IsStudent]

    def post(self, request):
        unavailable = _code_execution_unavailable_response()
        if unavailable is not None:
            return unavailable

        # Support both JSON body and FormData file upload
        if 'file' in request.FILES:
            uploaded_file = request.FILES['file']
            if uploaded_file.size > settings.EXECUTION_CODE_MAX_BYTES:
                return Response(
                    {'error': '代码超出系统大小上限', 'code': 'payload_too_large'},
                    status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                )
            try:
                code = uploaded_file.read().decode('utf-8')
            except UnicodeDecodeError:
                return Response(
                    {'error': '代码文件必须使用 UTF-8 编码'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            data = {
                'problem_id': request.data.get('problem_id', ''),
                'code': code,
            }
        else:
            data = request.data

        serializer = SubmissionCreateSerializer(data=data)
        if not serializer.is_valid():
            return Response(
                {'error': '参数错误', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        problem_id = serializer.validated_data['problem_id']
        code = serializer.validated_data['code']

        # 查找题目
        problem = get_visible_problem_or_404(
            request.user, problem_id, course='ai',
        )

        try:
            task, submission, created = enqueue_grade(
                user=request.user,
                problem=problem,
                code=code,
                idempotency_key=request.headers.get('Idempotency-Key'),
            )
        except InvalidTestSnapshot as exc:
            return Response(
                {'error': str(exc), 'code': 'invalid_test_snapshot'},
                status=status.HTTP_409_CONFLICT,
            )
        except ExecutionRequestError as exc:
            return _execution_error_response(exc)

        response_data = public_task_data(task)
        response_data.update({'submission_id': submission.id, 'created': created})
        return Response(response_data, status=status.HTTP_202_ACCEPTED)


class SubmissionHistoryView(APIView):
    """
    GET /api/ai/submissions/?problem_id=xxx
    获取某道题的提交历史
    """
    permission_classes = [IsStudent]

    def get(self, request):
        problem_id = request.query_params.get('problem_id')
        visible = visible_problems_for_student(
            Problem.objects.filter(course='ai'), request.user,
        )
        submissions = Submission.objects.filter(user=request.user, problem__in=visible)
        if problem_id:
            submissions = submissions.filter(problem__problem_id=problem_id)
        submissions = submissions.order_by('-submitted_at')[:20]
        serializer = SubmissionHistorySerializer(submissions, many=True)
        return Response(serializer.data)


class StudentScoresView(APIView):
    """
    GET /api/ai/scores/
    获取学生的所有成绩（每题最高分）
    """
    permission_classes = [IsStudent]

    def get(self, request):
        user = request.user
        course = request.query_params.get('course', 'ai')
        problem_id = request.query_params.get('problem_id')

        visible = visible_problems_for_student(
            Problem.objects.filter(course=course), user,
        )

        # 每道题的最好成绩（只取当前课程）
        scores = (
            Submission.objects.filter(user=user, problem__in=visible, score__isnull=False)
            .values('problem__problem_id')
            .annotate(
                best_score=Max('score'),
                attempts=Count('id')
            )
            .order_by('problem__problem_id')
        )

        result = []
        for item in scores:
            pid = item['problem__problem_id']
            best = item['best_score']
            result.append({
                'problem_id': pid,
                'best_score': best,
                'attempts': item['attempts'],
                'status': 'completed' if best >= 80 else 'attempted',
            })

        if problem_id:
            result = [r for r in result if r['problem_id'] == problem_id]

        return Response(result)


class StudentStatsView(APIView):
    """
    GET /api/ai/stats/
    获取学生的学习统计
    """
    permission_classes = [IsStudent]

    def get(self, request):
        user = request.user
        course = request.query_params.get('course', 'ai')

        if course == 'info':
            # 信息课：统计 QuizSession / QuizSubmission
            from info_tech.models import QuizSession, QuizSubmission

            user_grade = getattr(user, 'grade', '') or ''

            # 学生端统计只包含当前开放的小测；关闭后与列表保持一致，不再展示。
            # 年级过滤：SQLite 不支持 JSONField __contains，换为内存过滤
            all_visible = QuizSession.objects.filter(
                status=QuizSession.STATUS_OPEN, archived_at__isnull=True,
            )
            if user_grade:
                visible_sessions = [
                    s for s in all_visible
                    if (not s.visible_grades or user_grade in s.visible_grades)
                    and (
                        not s.visible_classes
                        or str(getattr(user, 'class_num', '') or '') in {
                            str(value) for value in s.visible_classes
                        }
                    )
                ]
                visible_ids = [s.id for s in visible_sessions]
            else:
                visible_sessions = list(all_visible)
                visible_ids = [s.id for s in visible_sessions]

            total_problems = len(visible_sessions)

            if visible_ids:
                settled_submissions = QuizSubmission.objects.filter(
                    user=user,
                    session_id__in=visible_ids,
                    status__in=(QuizSubmission.STATUS_SUBMITTED, QuizSubmission.STATUS_TIMED_OUT),
                ).order_by('session_id', '-attempt_no', '-id')
                latest_scores = {}
                for submission in settled_submissions:
                    latest_scores.setdefault(submission.session_id, submission.score)
                completed_problems = len(latest_scores)
                scores = list(latest_scores.values())
                avg_score = round(sum(scores) / len(scores), 1) if scores else 0
            else:
                completed_problems = 0
                avg_score = 0

            rank = 1
        else:
            # AI课：统计 Problem / Submission（原有逻辑）
            visible = visible_problems_for_student(
                Problem.objects.filter(course=course), user,
            )
            total_problems = visible.count()

            completed_problems = (
                Submission.objects.filter(user=user, score__gte=80, problem__in=visible)
                .values('problem')
                .distinct()
                .count()
            )

            avg_result = (
                Submission.objects.filter(user=user, problem__in=visible)
                .values('problem__problem_id')
                .annotate(best=Max('score'))
                .aggregate(avg=Avg('best'))
            )
            avg_score = round(avg_result['avg'] or 0, 1)

            # Rank: compare average best-score among classmates
            user_grade = getattr(user, 'grade', '') or ''
            user_class = getattr(user, 'class_num', '') or ''
            if user_grade and user_class:
                from users.models import CustomUser
                classmates = CustomUser.objects.filter(
                    grade=user_grade, class_num=user_class
                )
                mate_scores = []
                for mate in classmates:
                    m_avg = (
                        Submission.objects.filter(user=mate, problem__in=visible)
                        .values('problem__problem_id')
                        .annotate(best=Max('score'))
                        .aggregate(avg=Avg('best'))
                    )['avg'] or 0
                    mate_scores.append((mate.id, round(m_avg, 1)))
                mate_scores.sort(key=lambda x: x[1], reverse=True)
                rank = 1
                prev_score = None
                same_count = 0
                for uid, score in mate_scores:
                    if prev_score is not None and score < prev_score:
                        rank += same_count
                        same_count = 1
                    else:
                        same_count += 1
                    if uid == user.id:
                        break
                    prev_score = score
                else:
                    rank = len(mate_scores) + 1
            else:
                rank = 1

        return Response({
            'total_problems': total_problems,
            'completed_problems': completed_problems,
            'average_score': avg_score,
            'rank': rank,
        })


# ============================================================
# 老师管理端 API
# ============================================================

class AdminDashboardView(APIView):
    """
    GET /api/admin/dashboard/
    管理后台统计数据
    """
    permission_classes = [IsTeacher]

    def get(self, request):
        from users.models import CustomUser

        students = scope_students(CustomUser.objects.filter(role='student'), request.user)
        total_students = students.count()
        total_problems = Problem.objects.filter(archived_at__isnull=True).count()

        today = datetime.datetime.now().date()
        today_submissions = Submission.objects.filter(
            user__in=students, submitted_at__date=today
        ).count()

        avg_result = (
            Submission.objects.filter(user__in=students)
            .values('problem__problem_id')
            .annotate(best=Max('score'))
            .aggregate(avg=Avg('best'))
        )
        avg_score = round(avg_result['avg'] or 0, 1)

        return Response({
            'total_students': total_students,
            'total_problems': total_problems,
            'today_submissions': today_submissions,
            'avg_score': avg_score,
        })


class AdminProblemListView(APIView):
    """
    GET /api/admin/ai/problems/
    老师：题目列表
    POST /api/admin/ai/problems/sync/
    老师：从磁盘同步题目
    """
    permission_classes = [IsTeacher]

    def get(self, request):
        course = request.query_params.get('course', 'ai')
        problems = Problem.objects.filter(course=course).prefetch_related('audience_rules')
        include_archived = request.query_params.get('include_archived') == '1'
        if not (include_archived and is_platform_admin(request.user)):
            problems = problems.filter(archived_at__isnull=True)
        serializer = AdminProblemListSerializer(
            problems, many=True, context={'request': request},
        )
        return Response(serializer.data)

    def post(self, request):
        # 手动同步题目
        sync_result = Problem.sync_from_disk(actor=request.user)
        if hasattr(sync_result, 'as_dict'):
            result_data = sync_result.as_dict()
        else:
            # Keep test doubles and older integrations compatible during rollout.
            created, updated = sync_result
            result_data = {
                'created': created, 'updated': updated,
                'skipped': [], 'failed': [],
            }
        ProblemManagementAudit.objects.create(
            event_type='disk_sync',
            outcome='success',
            actor_user_id=request.user.pk,
            before_summary={},
            after_summary=result_data,
            source_ip=_source_ip(request),
        )
        return Response(result_data)


class AdminProblemDetailView(APIView):
    """
    GET /api/admin/ai/problems/<problem_id>/
    老师：查看单道题目详情
    DELETE /api/admin/ai/problems/<problem_id>/
    老师：删除题目
    """
    permission_classes = [IsTeacher]

    def _get_problem(self, request, problem_id):
        queryset = Problem.objects.filter(course='ai').prefetch_related('audience_rules')
        if not is_platform_admin(request.user):
            queryset = queryset.filter(archived_at__isnull=True)
        return get_object_or_404(queryset, problem_id=problem_id)

    def get(self, request, problem_id):
        problem = self._get_problem(request, problem_id)
        return Response(AdminProblemDetailSerializer(
            problem, context={'request': request},
        ).data)

    def patch(self, request, problem_id):
        serializer = ProblemContentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        expected_version = values.pop('expected_version')
        try:
            problem = edit_problem_content(
                actor=request.user,
                problem_id=problem_id,
                values=values,
                expected_version=expected_version,
                source_ip=_source_ip(request),
            )
        except ProblemManagementError as exc:
            return _management_error_response(exc)
        return Response(AdminProblemDetailSerializer(
            problem, context={'request': request},
        ).data)

    def delete(self, request, problem_id):
        serializer = ProblemVersionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            problem = archive_problem(
                actor=request.user,
                problem_id=problem_id,
                expected_version=serializer.validated_data['expected_version'],
                source_ip=_source_ip(request),
            )
        except ProblemManagementError as exc:
            return _management_error_response(exc)
        return Response({
            'message': f'题目 {problem.title or problem.problem_id} 已归档，历史成绩已保留',
            'management_version': problem.management_version,
        })


class AdminProblemPublicationView(APIView):
    permission_classes = [IsTeacher]

    def get(self, request, problem_id):
        problem = get_object_or_404(
            Problem.objects.filter(course='ai', archived_at__isnull=True).prefetch_related('audience_rules'),
            problem_id=problem_id,
        )
        try:
            data = publication_data(problem, request.user)
        except TeacherScopeError as exc:
            return Response({'error': exc.message, 'code': exc.code}, status=403)
        return Response(data)

    def patch(self, request, problem_id):
        if not is_platform_admin(request.user):
            forbidden_fields = {'all_school', 'publishing_suspended', 'scopes'} & set(request.data.keys())
            if forbidden_fields:
                ProblemManagementAudit.objects.create(
                    event_type='scope_update', outcome='denied',
                    actor_user_id=request.user.pk, problem_id=problem_id,
                    reason_code='admin_scope_forbidden', source_ip=_source_ip(request),
                )
                return Response(
                    {'error': '普通教师不能设置全校、跨年级或全局暂停', 'code': 'admin_scope_forbidden'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if request.data.get('grade') not in (None, ''):
                try:
                    require_teacher_grade(request.user, request.data.get('grade'))
                except TeacherScopeError as exc:
                    ProblemManagementAudit.objects.create(
                        event_type='scope_update', outcome='denied',
                        actor_user_id=request.user.pk, problem_id=problem_id,
                        reason_code=exc.code, source_ip=_source_ip(request),
                    )
                    return Response({'error': exc.message, 'code': exc.code}, status=403)
        serializer_class = (
            AdminProblemAudienceUpdateSerializer
            if is_platform_admin(request.user)
            else TeacherProblemAudienceUpdateSerializer
        )
        serializer = serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        expected_version = values.pop('expected_version')
        try:
            problem = update_problem_audience(
                actor=request.user,
                problem_id=problem_id,
                values=values,
                expected_version=expected_version,
                source_ip=_source_ip(request),
            )
            problem = Problem.objects.prefetch_related('audience_rules').get(pk=problem.pk)
            return Response(publication_data(problem, request.user))
        except (ProblemManagementError, TeacherScopeError) as exc:
            if isinstance(exc, TeacherScopeError):
                return Response({'error': exc.message, 'code': exc.code}, status=403)
            return _management_error_response(exc)


class AdminProblemRestoreView(APIView):
    permission_classes = [IsTeacher]

    def post(self, request, problem_id):
        serializer = ProblemVersionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            problem = restore_problem(
                actor=request.user,
                problem_id=problem_id,
                expected_version=serializer.validated_data['expected_version'],
                source_ip=_source_ip(request),
            )
        except ProblemManagementError as exc:
            return _management_error_response(exc)
        return Response({
            'message': f'题目 {problem.title or problem.problem_id} 已恢复，请确认范围后重新发布',
            'management_version': problem.management_version,
        })


class AdminProblemClassOptionsView(APIView):
    permission_classes = [IsTeacher]

    def get(self, request):
        requested_grade = request.query_params.get('grade')
        try:
            grade = require_teacher_grade(request.user, requested_grade)
            grade = normalize_grade(grade or requested_grade)
        except TeacherScopeError as exc:
            return Response({'error': exc.message, 'code': exc.code}, status=403)
        except Exception:
            return Response({'error': '年级不在允许范围内', 'code': 'invalid_grade'}, status=400)
        classes = list(
            CustomUser.objects.filter(role='student', grade=grade)
            .exclude(class_num__isnull=True).exclude(class_num='')
            .values_list('class_num', flat=True).distinct()
        )

        def natural_key(value):
            text = str(value)
            return (0, int(text)) if text.isdigit() else (1, text)

        return Response({'grade': grade, 'classes': sorted(classes, key=natural_key)})


class AdminStudentListView(APIView):
    """
    GET /api/admin/students/
    老师：学生列表
    """
    permission_classes = [IsTeacher]

    def get(self, request):
        from users.serializers import UserSerializer
        from users.models import CustomUser

        grade = request.query_params.get('grade')
        class_num = request.query_params.get('class_num')
        sort_by = request.query_params.get('sort_by', 'grade')
        order = request.query_params.get('order', 'asc')

        students = scope_students(
            CustomUser.objects.filter(role='student'), request.user,
        )
        if grade:
            students = students.filter(grade=grade)
        if class_num:
            students = students.filter(class_num=class_num)

        # 支持按 grade, class_num, username, student_number 排序
        allowed_fields = ['grade', 'class_num', 'username', 'student_number']
        if sort_by not in allowed_fields:
            sort_by = 'grade'
        if order == 'desc':
            sort_by = '-' + sort_by

        students = students.order_by(sort_by)
        serializer = UserSerializer(students, many=True)
        return Response(serializer.data)


class AdminStudentScoresView(APIView):
    """
    GET /api/admin/scores/?course_type=ai&problem_id=X
    老师：查看所有学生成绩，支持 course_type 过滤
    返回格式：{students: [{student_number, username, grade, class_num, best_score, ...}], problems: [...]}
    """
    permission_classes = [IsTeacher]

    def get(self, request):
        course_type = request.query_params.get('course_type', 'ai')  # 'ai' 或 'info'
        grade = request.query_params.get('grade')
        class_num = request.query_params.get('class_num')
        problem_id = request.query_params.get('problem_id')
        include_archived = (
            request.query_params.get('include_archived') == '1'
            and is_platform_admin(request.user)
        )

        # 只看学生（不含教师账号）
        scoped_students = scope_students(
            CustomUser.objects.filter(role='student'), request.user,
        )
        submissions = Submission.objects.filter(
            user__in=scoped_students, score__isnull=False,
        )
        if not include_archived:
            submissions = submissions.filter(problem__archived_at__isnull=True)

        if grade:
            submissions = submissions.filter(user__grade=grade)
        if class_num:
            submissions = submissions.filter(user__class_num=class_num)
        if problem_id:
            submissions = submissions.filter(problem__problem_id=problem_id)
        if course_type:
            submissions = submissions.filter(problem__course=course_type)

        # 构建学生映射：student_number -> {grade, class_num, username, display_name, scores}
        all_students = scoped_students
        if grade:
            all_students = all_students.filter(grade=grade)
        if class_num:
            all_students = all_students.filter(class_num=class_num)

        student_map = {}
        for s in all_students:
            key = s.student_number or s.username
            student_map[key] = {
                'student_number': s.student_number or '',
                'username': s.username,
                'display_name': getattr(s, 'display_name', '') or s.username,
                'grade': s.grade or '',
                'class_num': s.class_num or '',
                'scores': [],   # [{problem_id, score}]
                'best_score': None,
            }

        # 获取所有题目（如果有 problem_id 过滤则只返回该题）
        problems = Problem.objects.all()
        if course_type:
            problems = problems.filter(course=course_type)
        if problem_id:
            problems = problems.filter(problem_id=problem_id)
        if not include_archived:
            problems = problems.filter(archived_at__isnull=True)
        problems = problems.order_by('problem_id')
        problem_ids = [p.problem_id for p in problems]

        # 每学生每题取最高分
        scores = (
            submissions
            .values('user__username', 'user__student_number', 'problem__problem_id')
            .annotate(best_score=Max('score'))
            .order_by('user__username', 'problem__problem_id')
        )

        # 填入每道题的分数
        for s in scores:
            key = s['user__student_number'] or s['user__username']
            if key in student_map:
                pid = s['problem__problem_id']
                score_val = s['best_score']
                # 追加到 scores 数组
                student_map[key]['scores'].append({'problem_id': pid, 'score': score_val})
                # 同时更新 best_score（全局最高）
                if student_map[key]['best_score'] is None or score_val > student_map[key]['best_score']:
                    student_map[key]['best_score'] = score_val

        students = list(student_map.values())
        # 返回完整题目信息（problem_id + title）
        problem_list = [
            {'problem_id': p.problem_id, 'title': p.title or p.problem_id}
            for p in problems
        ]
        return Response({
            'students': students,
            'problems': problem_list,
        })


# ============================================================
# 代码执行端点
# ============================================================

class CodeRunRateThrottle(UserRateThrottle):
    """Per-user rate throttle: 3 requests per second"""
    rate = '3/second'


class CodeRunView(APIView):
    """
    POST /api/ai/run_code/
    Queue Python code for isolated execution with stdin support.

    Request body:
        {
            "code": "print('hello')",
            "stdin": ""  (optional)
        }

    Responses:
        202: {"task_id": "uuid", "status": "queued", "poll_after_ms": 500}
        400/413: invalid or oversized payload
        429: request throttle or per-user active queue limit exceeded
        503: code execution is disabled
    """
    permission_classes = [IsStudent]
    throttle_classes = [CodeRunRateThrottle]

    def post(self, request):
        unavailable = _code_execution_unavailable_response()
        if unavailable is not None:
            return unavailable

        serializer = CodeRunCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': '参数错误', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            task, created = enqueue_run(
                user=request.user,
                code=serializer.validated_data['code'],
                stdin=serializer.validated_data['stdin'],
                idempotency_key=request.headers.get('Idempotency-Key'),
            )
        except ExecutionRequestError as exc:
            return _execution_error_response(exc)

        response_data = public_task_data(task)
        response_data['created'] = created
        return Response(response_data, status=status.HTTP_202_ACCEPTED)
