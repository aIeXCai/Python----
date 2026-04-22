import os
import uuid
import datetime
from django.conf import settings
from django.db.models import Max, Avg, Count
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import Problem, Submission, grade_submission
from .serializers import (
    ProblemListSerializer,
    ProblemDetailSerializer,
    SubmissionCreateSerializer,
    SubmissionHistorySerializer,
    ScoreSerializer,
    StudentStatsSerializer,
    AdminStatsSerializer,
)


class IsTeacher(permissions.BasePermission):
    """老师权限"""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'teacher'
        )


# ============================================================
# 学生端 API
# ============================================================

class ProblemListView(APIView):
    """
    GET /api/ai/problems/?course=ai
    获取题目列表（学生用）
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # 先从磁盘同步题目
        Problem.sync_from_disk()
        course = request.query_params.get('course', 'ai')
        problems = Problem.objects.filter(course=course)
        serializer = ProblemListSerializer(problems, many=True)
        return Response(serializer.data)


class ProblemDetailView(APIView):
    """
    GET /api/ai/problems/<problem_id>/
    获取题目详情（含测试点）
    """
    permission_classes = [permissions.IsAuthenticated]

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
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = SubmissionCreateSerializer(data=request.data)
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

        # 保存代码到 submissions/ 目录
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = f"{request.user.username}_{problem_id}_{timestamp}_{uuid.uuid4().hex[:8]}.py"
        submissions_dir = settings.BASE_DIR / 'submissions'
        submissions_dir.mkdir(exist_ok=True)
        submission_path = submissions_dir / safe_filename

        with open(submission_path, 'w', encoding='utf-8') as f:
            f.write(code)

        # 批改
        try:
            ok, result_text, score = grade_submission(str(submission_path), problem)
        except Exception as e:
            Submission.objects.create(
                user=request.user,
                problem=problem,
                code=code,
                score=0,
                status='error',
                error_message=str(e),
            )
            return Response({
                'success': False,
                'score': 0,
                'status': 'error',
                'detail': f'批改系统错误：{str(e)}',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 根据结果确定状态
        if not ok:
            submit_status = 'error'
        elif score == 100:
            submit_status = 'accepted'
        elif score == 0:
            submit_status = 'wrong_answer'
        else:
            submit_status = 'wrong_answer'

        # 保存提交记录
        submission = Submission.objects.create(
            user=request.user,
            problem=problem,
            code=code,
            score=score,
            status=submit_status,
            error_message=result_text if score < 100 else '',
        )

        return Response({
            'success': True,
            'submission_id': submission.id,
            'score': score,
            'status': submit_status,
            'detail': result_text,
        })


class SubmissionHistoryView(APIView):
    """
    GET /api/ai/submissions/?problem_id=xxx
    获取某道题的提交历史
    """
    permission_classes = [permissions.IsAuthenticated]

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
    permission_classes = [permissions.IsAuthenticated]

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
            Submission.objects.filter(user=user, problem__course=course)
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
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        course = request.query_params.get('course', 'ai')

        # 总题目数（按课程）
        total_problems = Problem.objects.filter(course=course).count()

        # 已完成题目数（>=80分，按课程）
        completed_problems = (
            Submission.objects.filter(user=user, score__gte=80, problem__course=course)
            .values('problem')
            .distinct()
            .count()
        )

        # 平均分（只算当前课程）
        avg_result = (
            Submission.objects.filter(user=user, problem__course=course)
            .values('problem__problem_id')
            .annotate(best=Max('score'))
            .aggregate(avg=Avg('best'))
        )
        avg_score = round(avg_result['avg'] or 0, 1)

        # 班级排名
        # 获取同班级其他同学的平均分
        same_class_students = (
            Problem.sync_from_disk()
        )
        # 简单实现：统计班级内比自己平均分高的学生数量
        my_avg = avg_score
        rank = 1  # 默认排名

        return Response({
            'total_problems': total_problems,
            'completed_problems': completed_problems,
            'average_score': my_avg,
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

        total_students = CustomUser.objects.filter(role='student').count()
        total_problems = Problem.objects.count()

        today = datetime.datetime.now().date()
        today_submissions = Submission.objects.filter(
            submitted_at__date=today
        ).count()

        avg_result = (
            Submission.objects
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
        Problem.sync_from_disk()
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

        students = CustomUser.objects.filter(role='student')
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
        submissions = Submission.objects.filter(user__role='student')

        if grade:
            submissions = submissions.filter(user__grade=grade)
        if class_num:
            submissions = submissions.filter(user__class_num=class_num)
        if problem_id:
            submissions = submissions.filter(problem__problem_id=problem_id)
        if course_type:
            submissions = submissions.filter(problem__course=course_type)

        # 构建学生映射：student_number -> {grade, class_num, username, display_name, scores}
        from users.models import CustomUser
        all_students = CustomUser.objects.filter(role='student')
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

        # 获取所有题目
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
