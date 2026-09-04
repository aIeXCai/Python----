import datetime
from django.conf import settings
from django.db.models import Max, Avg, Count, OuterRef, Subquery, Q
from rest_framework import status
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import Problem, Submission
from .serializers import (
    ProblemListSerializer,
    ProblemDetailSerializer,
    SubmissionCreateSerializer,
    SubmissionHistorySerializer,
    ScoreSerializer,
    StudentStatsSerializer,
    AdminStatsSerializer,
)
from execution.serializers import CodeRunCreateSerializer, public_task_data
from execution.services import ExecutionRequestError, enqueue_grade, enqueue_run
from execution.snapshots import InvalidTestSnapshot
from users.permissions import IsStudent, IsTeacher
from users.scopes import scope_students
from users.models import CustomUser


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
        problems = Problem.objects.filter(course=course)
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
        try:
            problem = Problem.objects.get(problem_id=problem_id, course=course)
        except Problem.DoesNotExist:
            return Response(
                {'error': '题目不存在'},
                status=status.HTTP_404_NOT_FOUND
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
        try:
            problem = Problem.objects.get(problem_id=problem_id)
        except Problem.DoesNotExist:
            return Response(
                {'error': '题目不存在'},
                status=status.HTTP_404_NOT_FOUND
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
        submissions = Submission.objects.filter(user=request.user)
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

        # 过滤指定课程的题目
        course_problem_ids = list(
            Problem.objects.filter(course=course).values_list('problem_id', flat=True)
        )

        # 每道题的最好成绩（只取当前课程）
        scores = (
            Submission.objects.filter(user=user, problem__course=course, score__isnull=False)
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
            total_problems = Problem.objects.filter(course=course).count()

            completed_problems = (
                Submission.objects.filter(user=user, score__gte=80, problem__course=course)
                .values('problem')
                .distinct()
                .count()
            )

            avg_result = (
                Submission.objects.filter(user=user, problem__course=course)
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
                        Submission.objects.filter(user=mate, problem__course=course)
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
        total_problems = Problem.objects.count()

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
        problems = Problem.objects.filter(course=course)
        serializer = ProblemListSerializer(problems, many=True)
        return Response(serializer.data)

    def post(self, request):
        # 手动同步题目
        created, updated = Problem.sync_from_disk()
        return Response({
            'created': created,
            'updated': updated,
        })


class AdminProblemDetailView(APIView):
    """
    GET /api/admin/ai/problems/<problem_id>/
    老师：查看单道题目详情
    DELETE /api/admin/ai/problems/<problem_id>/
    老师：删除题目
    """
    permission_classes = [IsTeacher]

    def get(self, request, problem_id):
        try:
            problem = Problem.objects.get(problem_id=problem_id)
        except Problem.DoesNotExist:
            return Response({'error': '题目不存在'}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'problem_id': problem.problem_id,
            'title': problem.title,
            'description': problem.description,
            'difficulty': problem.difficulty,
            'course': problem.course,
            'created_at': problem.created_at,
        })

    def delete(self, request, problem_id):
        try:
            problem = Problem.objects.get(problem_id=problem_id)
        except Problem.DoesNotExist:
            return Response({'error': '题目不存在'}, status=status.HTTP_404_NOT_FOUND)
        title = problem.title
        problem.delete()
        return Response({'message': f'题目 {title} 已删除'})


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

        # 只看学生（不含教师账号）
        scoped_students = scope_students(
            CustomUser.objects.filter(role='student'), request.user,
        )
        submissions = Submission.objects.filter(
            user__in=scoped_students, score__isnull=False,
        )

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
        if problem_id:
            problems = Problem.objects.filter(course=course_type, problem_id=problem_id).order_by('problem_id')
        else:
            problems = Problem.objects.filter(course=course_type).order_by('problem_id') if course_type else Problem.objects.all().order_by('problem_id')
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
