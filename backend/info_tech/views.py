from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count, Avg, Max, Min

from .models import Unit, Question, QuizSession, QuizSubmission
from .serializers import (
    UnitSerializer, QuestionSerializer,
    QuestionCreateSerializer, QuestionImportSerializer,
    QuizSessionSerializer, QuizSessionCreateSerializer,
    QuizSessionToggleSerializer,
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


class UnitUpdateView(APIView):
    """PUT /api/admin/info/units/<id>/ 编辑单元"""
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        if request.user.role != 'teacher':
            return Response({'error': '仅老师可操作'}, status=403)
        try:
            unit = Unit.objects.get(pk=pk)
        except Unit.DoesNotExist:
            return Response({'error': '单元不存在'}, status=404)
        unit.name = request.data.get('name', unit.name)
        unit.display_name = request.data.get('display_name', unit.display_name)
        unit.order = request.data.get('order', unit.order)
        unit.save()
        serializer = UnitSerializer(unit)
        return Response(serializer.data)


class UnitDeleteView(APIView):
    """DELETE /api/admin/info/units/<id>/delete/ 删除单元"""
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        if request.user.role != 'teacher':
            return Response({'error': '仅老师可操作'}, status=403)
        try:
            unit = Unit.objects.get(pk=pk)
        except Unit.DoesNotExist:
            return Response({'error': '单元不存在'}, status=404)
        unit.delete()
        return Response(status=204)


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
            'errors': result['errors'][:20]
        }, status=201)


# ─── QuizSession API ──────────────────────────────────────────────────────────

class QuizSessionListView(APIView):
    """GET /api/admin/info/sessions/ 小测列表"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sessions = QuizSession.objects.all().prefetch_related('units').order_by('-created_at')
        serializer = QuizSessionSerializer(sessions, many=True)
        return Response(serializer.data)


class QuizSessionCreateView(APIView):
    """POST /api/admin/info/sessions/create/ 创建小测"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != 'teacher':
            return Response({'error': '仅老师可操作'}, status=403)

        serializer = QuizSessionCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            session = serializer.save()
            return Response(QuizSessionSerializer(session).data, status=201)
        return Response(serializer.errors, status=400)


class QuizSessionUpdateView(APIView):
    """PUT /api/admin/info/sessions/{id}/ 修改小测"""
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        if request.user.role != 'teacher':
            return Response({'error': '仅老师可操作'}, status=403)

        try:
            session = QuizSession.objects.prefetch_related('units').get(pk=pk)
        except QuizSession.DoesNotExist:
            return Response({'error': '小测不存在'}, status=404)

        serializer = QuizSessionCreateSerializer(session, data=request.data, context={'request': request})
        if serializer.is_valid():
            session = serializer.save()
            return Response(QuizSessionSerializer(session).data)
        return Response(serializer.errors, status=400)


class QuizSessionDeleteView(APIView):
    """DELETE /api/admin/info/sessions/{id}/delete/ 删除小测"""
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        if request.user.role != 'teacher':
            return Response({'error': '仅老师可操作'}, status=403)

        try:
            session = QuizSession.objects.get(pk=pk)
            session.delete()
            return Response({'detail': '删除成功'})
        except QuizSession.DoesNotExist:
            return Response({'error': '小测不存在'}, status=404)


class QuizSessionToggleView(APIView):
    """PATCH /api/admin/info/sessions/{id}/toggle/ 切换可见性"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        if request.user.role != 'teacher':
            return Response({'error': '仅老师可操作'}, status=403)

        try:
            session = QuizSession.objects.get(pk=pk)
        except QuizSession.DoesNotExist:
            return Response({'error': '小测不存在'}, status=404)

        serializer = QuizSessionToggleSerializer(data=request.data)
        if serializer.is_valid():
            session.is_visible = serializer.validated_data['is_visible']
            session.visible_grades = serializer.validated_data.get('visible_grades', [])
            session.save()
            return Response(QuizSessionSerializer(session).data)
        return Response(serializer.errors, status=400)


# ─── 成绩统计 API ─────────────────────────────────────────────────────────────

class QuizStatsOverviewView(APIView):
    """GET /api/admin/info/stats/overview/ 全局概览"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'teacher':
            return Response({'error': '仅老师可操作'}, status=403)

        total_sessions = QuizSession.objects.count()
        total_submissions = QuizSubmission.objects.count()
        avg_score = QuizSubmission.objects.aggregate(avg=Avg('score'))['avg'] or 0
        scores = list(QuizSubmission.objects.values_list('score', flat=True))
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

        # 按年级统计
        grade_stats = QuizSubmission.objects.values('grade').annotate(
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
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'teacher':
            return Response({'error': '仅老师可操作'}, status=403)

        sessions = QuizSession.objects.all().order_by('-created_at')
        result = []
        for s in sessions:
            subs = s.quizsubmission_set.all()
            total = subs.count()
            result.append({
                'session_id': s.id,
                'title': s.title,
                'total_submissions': total,
                'avg_score': round(subs.aggregate(avg=Avg('score'))['avg'], 1) if total > 0 else None,
                'max_score': subs.aggregate(max=Max('score'))['max'],
                'min_score': subs.aggregate(min=Min('score'))['min'],
            })

        return Response(result)


class QuizStatsSessionDetailView(APIView):
    """GET /api/admin/info/stats/sessions/<id>/ 某小测详细统计"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if request.user.role != 'teacher':
            return Response({'error': '仅老师可操作'}, status=403)

        try:
            session = QuizSession.objects.get(pk=pk)
        except QuizSession.DoesNotExist:
            return Response({'error': '小测不存在'}, status=404)

        subs = session.quizsubmission_set.all()
        total = subs.count()
        if total == 0:
            return Response({
                'session_id': session.id, 'title': session.title,
                'total_submissions': 0,
                'avg_score': None, 'max_score': None, 'min_score': None,
                'by_grade': [], 'question_stats': []
            })

        # 按年级
        by_grade = subs.values('grade').annotate(
            count=Count('id'),
            avg_score=Avg('score')
        ).order_by('grade')

        # 按题目错误率（只用本次提交的答案里的 question_id）
        import json
        q_correct = {}
        q_total = {}
        for sub in subs:
            answers = json.loads(sub.answers_json) if sub.answers_json else {}
            for qid_str, user_ans in answers.items():
                qid = int(qid_str)
                q_total[qid] = q_total.get(qid, 0) + 1
                try:
                    q = Question.objects.get(pk=qid)
                    if user_ans.upper() == q.answer.upper():
                        q_correct[qid] = q_correct.get(qid, 0) + 1
                except Question.DoesNotExist:
                    pass

        all_qids = set(list(q_correct.keys()) + list(q_total.keys()))
        question_stats = []
        for qid in all_qids:
            try:
                q = Question.objects.get(pk=qid)
            except Question.DoesNotExist:
                continue
            attempted = q_total.get(qid, 0)
            correct = q_correct.get(qid, 0)
            question_stats.append({
                'question_id': qid,
                'text': q.text[:60],
                'difficulty': q.difficulty,
                'category': q.category,
                'attempted': attempted,
                'correct': correct,
                'correct_rate': round(correct / attempted * 100, 1) if attempted > 0 else 0,
            })

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
        })


class QuizStatsGradeView(APIView):
    """GET /api/admin/info/stats/grade/<grade>/ 按年级详细统计"""
    permission_classes = [IsAuthenticated]

    def get(self, request, grade):
        if request.user.role != 'teacher':
            return Response({'error': '仅老师可操作'}, status=403)

        subs = QuizSubmission.objects.filter(grade=grade)
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
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'teacher':
            return Response({'error': '仅老师可操作'}, status=403)

        grade = request.query_params.get('grade')
        class_num = request.query_params.get('class_num')
        session_id = request.query_params.get('session_id')

        subs = QuizSubmission.objects.select_related('user', 'session').order_by('user__grade', 'user__class_num', 'user__student_number')

        if grade:
            subs = subs.filter(grade=grade)
        if class_num:
            subs = subs.filter(user__class_num=int(class_num))
        if session_id:
            subs = subs.filter(session_id=int(session_id))

        if not subs.exists():
            return Response({'students': [], 'sessions': []})

        # 收集所有涉及的 session
        session_ids = sorted(set(subs.values_list('session_id', flat=True)))
        sessions = QuizSession.objects.filter(id__in=session_ids).order_by('created_at')
        session_titles = {s.id: s.title for s in sessions}

        # 按学生聚合
        from collections import defaultdict
        student_map = defaultdict(lambda: {'scores': {}})
        for sub in subs:
            key = (sub.user_id, sub.user.display_name, sub.grade, sub.user.class_num, sub.user.student_number)
            student_map[key]['display_name'] = sub.user.display_name
            student_map[key]['grade'] = sub.grade
            student_map[key]['class_num'] = sub.user.class_num
            student_map[key]['student_number'] = sub.user.student_number
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
