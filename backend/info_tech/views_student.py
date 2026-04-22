import random
import json
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Max

from .models import QuizSession, QuizSubmission, Question


# ─── 学生端：小测列表 ─────────────────────────────────────────────────────────

class QuizListView(APIView):
    """GET /api/info/quizzes/ 可见小测列表（含是否已做/最高分）"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        user_grade = user.managed_grade

        all_sessions = QuizSession.objects.filter(is_visible=True)

        # 年级可见性过滤：visible_grades=[] 全部可见，否则只显示该年级
        visible = []
        for s in all_sessions:
            vg = s.visible_grades
            if not vg:  # [] = 全部可见
                visible.append(s)
            elif user_grade and user_grade in vg:
                visible.append(s)

        result = []
        for session in visible:
            subs = QuizSubmission.objects.filter(user=user, session=session)
            best = subs.aggregate(Max('score'))['score__max'] if subs.exists() else None
            latest_id = subs.order_by('-submitted_at').values_list('id', flat=True).first()
            unit_names = [u.display_name for u in session.units.all()]
            result.append({
                'id': session.id,
                'title': session.title,
                'unit_names': unit_names,
                'num_questions': session.num_questions,
                'time_limit': session.time_limit,
                'is_visible': session.is_visible,
                'best_score': best,
                'submitted': subs.exists(),
                'latest_submission_id': latest_id,
            })

        return Response(result)


# ─── 学生端：小测详情（随机抽题+选项打乱）────────────────────────────────────

class QuizDetailView(APIView):
    """GET /api/info/quizzes/<id>/ 小测详情（含随机抽题+打乱选项）"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        user = request.user

        try:
            session = QuizSession.objects.prefetch_related('units').get(pk=pk, is_visible=True)
        except QuizSession.DoesNotExist:
            return Response({'error': '小测不存在或未发布'}, status=404)

        # 年级可见性
        vg = session.visible_grades
        if vg and user.managed_grade and user.managed_grade not in vg:
            return Response({'error': '无权限访问'}, status=403)

        # 收集所有可用题目
        all_qs = list(Question.objects.filter(unit__in=session.units.all()))

        # 按难度分层
        ratio = session.difficulty_ratio or {}
        total = sum(ratio.values())
        if total == 0:
            total = len(all_qs) or 1
            ratio = {'easy': total}

        selected = []
        remaining = {k: list(v) for k, v in self._group_by_difficulty(all_qs).items()}

        for diff, count in ratio.items():
            count = int(count)
            pool = remaining.get(diff, [])
            random.shuffle(pool)
            selected.extend(pool[:count])

        # 不够就跨难度补
        random.shuffle(selected)
        if len(selected) < session.num_questions:
            shortfall = session.num_questions - len(selected)
            others = [q for q in all_qs if q not in selected]
            random.shuffle(others)
            selected.extend(others[:shortfall])

        selected = selected[:session.num_questions]
        random.shuffle(selected)

        # 选项打乱映射
        shuffled_questions = []
        for q in selected:
            opts = ['A', 'B', 'C', 'D']
            shuffled_opts = opts[:]
            random.shuffle(shuffled_opts)
            opt_map = {'A': q.option_a, 'B': q.option_b, 'C': q.option_c, 'D': q.option_d}
            shuffled_texts = [opt_map[o] for o in shuffled_opts]
            # 记录打乱后的正确选项在列表中的位置
            correct_opt = shuffled_opts[shuffled_opts.index(q.answer)]

            shuffled_questions.append({
                'id': q.id,
                'text': q.text,
                'options': {
                    'A': shuffled_texts[0],
                    'B': shuffled_texts[1],
                    'C': shuffled_texts[2],
                    'D': shuffled_texts[3],
                },
                'correct_answer': correct_opt,  # 打乱后的字母
                'shuffled_order': shuffled_opts,  # 原始字母→打乱后位置
                'category': q.category,
            })

        return Response({
            'session_id': session.id,
            'title': session.title,
            'num_questions': session.num_questions,
            'time_limit': session.time_limit,
            'questions': shuffled_questions,
        })

    def _group_by_difficulty(self, questions):
        return {
            'easy': [q for q in questions if q.difficulty == 'easy'],
            'medium': [q for q in questions if q.difficulty == 'medium'],
            'hard': [q for q in questions if q.difficulty == 'hard'],
        }


# ─── 学生端：提交小测 ─────────────────────────────────────────────────────────

class QuizSubmitView(APIView):
    """POST /api/info/quizzes/<id>/submit/ 提交答案并评分"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        user = request.user

        try:
            session = QuizSession.objects.get(pk=pk, is_visible=True)
        except QuizSession.DoesNotExist:
            return Response({'error': '小测不存在或未发布'}, status=404)

        # 年级可见性
        vg = session.visible_grades
        if vg and user.managed_grade and user.managed_grade not in vg:
            return Response({'error': '无权限访问'}, status=403)

        data = request.data
        answers = data.get('answers', {})  # {question_id: 'A'/'B'/'C'/'D'}（原始字母）
        shuffled_answers = data.get('shuffled_answers', {})  # {question_id: 'A'/'B'/'C'/'D'}（打乱后字母）
        shuffled_orders = data.get('shuffled_orders', {})  # {question_id: ['C','A','D','B']}（打乱顺序）

        # 验证题目都来自本 session
        session_question_ids = set(
            Question.objects.filter(unit__in=session.units.all()).values_list('id', flat=True)
        )

        # 评分（此时 answers 已经是原始字母）
        correct_count = 0
        total_count = len(answers)
        details = []

        for qid_str, user_ans in answers.items():
            qid = int(qid_str)
            if qid not in session_question_ids:
                continue
            try:
                q = Question.objects.get(pk=qid)
            except Question.DoesNotExist:
                continue

            is_correct = (user_ans.upper() == q.answer.upper())
            if is_correct:
                correct_count += 1

            details.append({
                'question_id': qid,
                'user_answer': user_ans.upper(),
                'correct_answer': q.answer,
                'is_correct': is_correct,
                'text': q.text,
                'explanation': q.explanation,
                'option_a': q.option_a,
                'option_b': q.option_b,
                'option_c': q.option_c,
                'option_d': q.option_d,
            })

        score = round(correct_count / total_count * 100, 1) if total_count > 0 else 0

        # answers_json 存三份：原始答案（评分用）+ 打乱后答案 + 每题打乱顺序（显示用）
        answers_payload = json.dumps({
            'answers': answers,
            'shuffled': shuffled_answers,
            'shuffled_orders': shuffled_orders,
        })

        # 保存提交记录（最新覆盖，用 submitted_at 排序取最新）
        submission = QuizSubmission.objects.create(
            user=user,
            session=session,
            grade=user.managed_grade or user.grade or '',
            score=score,
            correct_count=correct_count,
            total_count=total_count,
            answers_json=answers_payload,
        )

        return Response({
            'submission_id': submission.id,
            'score': score,
            'correct_count': correct_count,
            'total_count': total_count,
            'details': details,
        }, status=201)


# ─── 学生端：成绩查看 ─────────────────────────────────────────────────────────

class QuizResultView(APIView):
    """GET /api/info/quizzes/<id>/result/ 查看我的成绩"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        user = request.user

        try:
            session = QuizSession.objects.get(pk=pk)
        except QuizSession.DoesNotExist:
            return Response({'error': '小测不存在'}, status=404)

        sub = QuizSubmission.objects.filter(user=user, session=session).order_by('-submitted_at').first()
        if not sub:
            return Response({'error': '暂无成绩'}, status=404)

        # answers_json 新格式：{answers: {qid: 原始字母}, shuffled: {qid: 打乱后字母}, shuffled_orders: {qid: ['C','A','D','B']}}
        raw = json.loads(sub.answers_json)
        if isinstance(raw, dict) and 'answers' in raw:
            answers_map = raw.get('answers', {})
            shuffled_map = raw.get('shuffled', {})
            shuffled_orders_map = raw.get('shuffled_orders', {})
        else:
            # 兼容旧格式
            answers_map = raw
            shuffled_map = {}
            shuffled_orders_map = {}

        details = []
        for qid_str, user_ans in answers_map.items():
            qid = int(qid_str)
            try:
                q = Question.objects.get(pk=qid)
            except Question.DoesNotExist:
                continue

            is_correct = (user_ans.upper() == q.answer.upper())

            # 构造打乱后的选项（如果有 shuffled_order）
            order = shuffled_orders_map.get(str(qid)) or shuffled_orders_map.get(qid)
            if order:
                # order = ['C','A','D','B']：display A=text_C, display B=text_A, ...
                opt_map = {'A': q.option_a, 'B': q.option_b, 'C': q.option_c, 'D': q.option_d}
                user_shuffled = shuffled_map.get(str(qid)) or ''
                # order = ['B','C','D','A']：order[i] = 显示字母 chr(65+i) 的原始字母
                # 找原始答案字母在打乱后出现在哪个显示位置
                correct_display = chr(65 + order.index(q.answer.upper())) if q.answer.upper() in 'ABCD' else q.answer
                # 答错了：只标正确答案，不标用户选的（避免打乱后重叠）
                user_display = None
                options = {}
                for i, letter in enumerate(order):
                    display_letter = chr(65 + i)  # 0→A, 1→B, 2→C, 3→D
                    options[display_letter] = {
                        'text': opt_map.get(letter, ''),
                        'is_user_answer': (display_letter == user_display),
                        'is_correct_answer': (display_letter == correct_display),
                    }
            else:
                # 无打乱顺序，使用原始选项
                options = {
                    'A': {'text': q.option_a, 'is_user_answer': (user_ans.upper() == 'A'), 'is_correct_answer': (q.answer == 'A')},
                    'B': {'text': q.option_b, 'is_user_answer': (user_ans.upper() == 'B'), 'is_correct_answer': (q.answer == 'B')},
                    'C': {'text': q.option_c, 'is_user_answer': (user_ans.upper() == 'C'), 'is_correct_answer': (q.answer == 'C')},
                    'D': {'text': q.option_d, 'is_user_answer': (user_ans.upper() == 'D'), 'is_correct_answer': (q.answer == 'D')},
                }

            details.append({
                'question_id': qid,
                'text': q.text,
                'user_answer': user_ans.upper(),      # 原始字母（用于判断）
                'correct_answer': q.answer,           # 原始字母
                'is_correct': is_correct,
                'explanation': q.explanation,
                'options': options,                    # 打乱后的选项（display letter → text + 高亮标记）
            })

        return Response({
            'submission_id': sub.id,
            'quiz_title': session.title,
            'score': sub.score,
            'correct_count': sub.correct_count,
            'total_count': sub.total_count,
            'submitted_at': sub.submitted_at,
            'question_results': details,
        })
