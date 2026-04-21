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
    GET /api/ai/problems/
    获取题目列表（学生用）
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # 先从磁盘同步题目
        Problem.sync_from_disk()
        problems = Problem.objects.all()
        serializer = ProblemListSerializer(problems, many=True)
        return Response(serializer.data)


class ProblemDetailView(APIView):
    """
    GET /api/ai/problems/<problem_id>/
    获取题目详情（含测试点）
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, problem_id):
        try:
            problem = Problem.objects.get(problem_id=problem_id)
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
        problem_id = request.query_params.get('problem_id')

        # 每道题的最好成绩
        scores = (
            Submission.objects.filter(user=user)
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

        # 总题目数
        total_problems = Problem.objects.count()

        # 已完成题目数（>=80分）
        completed_problems = (
            Submission.objects.filter(user=user, score__gte=80)
            .values('problem')
            .distinct()
            .count()
        )

        # 平均分
        avg_result = (
            Submission.objects.filter(user=user)
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
        problems = Problem.objects.all()
        serializer = ProblemListSerializer(problems, many=True)
        return Response(serializer.data)

    def post(self, request):
        # 手动同步题目
        created, updated = Problem.sync_from_disk()
        return Response({
            'created': created,
            'updated': updated,
        })


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

        students = CustomUser.objects.filter(role='student')
        if grade:
            students = students.filter(grade=grade)
        if class_num:
            students = students.filter(class_num=class_num)

        students = students.order_by('grade', 'class_num', 'username')
        serializer = UserSerializer(students, many=True)
        return Response(serializer.data)


class AdminStudentScoresView(APIView):
    """
    GET /api/admin/scores/
    老师：查看所有学生成绩
    """
    permission_classes = [IsTeacher]

    def get(self, request):
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

        # 每学生每题最新成绩
        data = (
            submissions
            .values('user__username', 'user__grade', 'user__class_num', 'problem__problem_id')
            .annotate(best_score=Max('score'))
            .order_by('user__grade', 'user__class_num', 'user__username', 'problem__problem_id')
        )

        return Response(data)
