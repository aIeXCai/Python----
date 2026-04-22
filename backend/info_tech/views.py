from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q

from .models import Unit, Question
from .serializers import (
    UnitSerializer, QuestionSerializer,
    QuestionCreateSerializer, QuestionImportSerializer
)


# ─── 教师权限mixin ────────────────────────────────────────────────────────────
class TeacherPermission:
    """仅允许 role=teacher 的用户"""
    def get_permissions(self):
        perms = super().get_permissions()
        perms[0].is_teacher_only = True
        return perms


# ─── Unit API ────────────────────────────────────────────────────────────────
class UnitListView(APIView):
    """GET /api/admin/info/units/ 列出所有单元"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        units = Unit.objects.all().order_by('order')
        serializer = UnitSerializer(units, many=True)
        return Response(serializer.data)


class UnitCreateView(APIView):
    """POST /api/admin/info/units/ 新增单元"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != 'teacher':
            return Response({'error': '仅老师可操作'}, status=403)

        serializer = UnitSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


# ─── Question API ─────────────────────────────────────────────────────────────
class QuestionListView(APIView):
    """GET /api/admin/info/questions/ 题库列表（支持过滤）"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Question.objects.all()

        # 按单元过滤
        unit_name = request.query_params.get('unit')
        if unit_name:
            qs = qs.filter(unit__name=unit_name)

        # 按难度过滤
        difficulty = request.query_params.get('difficulty')
        if difficulty:
            qs = qs.filter(difficulty=difficulty)

        # 全文搜索
        q = request.query_params.get('q')
        if q:
            qs = qs.filter(Q(text__icontains=q) | Q(category__icontains=q))

        qs = qs.select_related('unit').order_by('id')
        serializer = QuestionSerializer(qs, many=True)
        return Response(serializer.data)


class QuestionCreateView(APIView):
    """POST /api/admin/info/questions/ 新增单题"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != 'teacher':
            return Response({'error': '仅老师可操作'}, status=403)

        serializer = QuestionCreateSerializer(data=request.data)
        if serializer.is_valid():
            question = serializer.save()
            return Response(QuestionSerializer(question).data, status=201)
        return Response(serializer.errors, status=400)


class QuestionUpdateView(APIView):
    """PUT /api/admin/info/questions/{id}/ 修改题目"""
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        if request.user.role != 'teacher':
            return Response({'error': '仅老师可操作'}, status=403)

        try:
            question = Question.objects.get(pk=pk)
        except Question.DoesNotExist:
            return Response({'error': '题目不存在'}, status=404)

        serializer = QuestionCreateSerializer(question, data=request.data)
        if serializer.is_valid():
            question = serializer.save()
            return Response(QuestionSerializer(question).data)
        return Response(serializer.errors, status=400)


class QuestionDeleteView(APIView):
    """DELETE /api/admin/info/questions/{id}/ 删除题目"""
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        if request.user.role != 'teacher':
            return Response({'error': '仅老师可操作'}, status=403)

        try:
            question = Question.objects.get(pk=pk)
            question.delete()
            return Response({'detail': '删除成功'})
        except Question.DoesNotExist:
            return Response({'error': '题目不存在'}, status=404)


class QuestionImportView(APIView):
    """POST /api/admin/info/questions/import/ 批量导入 JSON"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != 'teacher':
            return Response({'error': '仅老师可操作'}, status=403)

        serializer = QuestionImportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        result = serializer.save()
        unit_created = serializer.validated_data.get('unit_created', False)
        msg = f"成功导入 {result['imported']} 题"
        if result['errors']:
            msg += f"，{len(result['errors'])} 题有错误"
        if unit_created:
            msg += f"（新建单元: {serializer.validated_data['unit'].name}）"

        return Response({
            'detail': msg,
            'imported': result['imported'],
            'unit_created': unit_created,
            'errors': result['errors'][:20]  # 最多返回20条错误
        }, status=201)
