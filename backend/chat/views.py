import json
import time
import threading
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from openai import OpenAI

from .models import ChatSession, ChatMessage
from users.permissions import IsStudent

# 并发控制：最多 3 路同时打到 MiniMax
_semaphore = threading.Semaphore(3)


def _build_system_prompt(context):
    """根据页面上下文构建 system prompt"""
    # 基础人设（三段共用）
    PERSONA = (
        '你是一位名叫"小 P"的 AI 编程老师，你的学生是八年级（初二）的中学生，'
        '他们对 Python 编程零基础，这是他们人生中第一次接触代码。\n\n'
        '## 你的教学风格\n'
        '1. 多用生活中的类比来解释编程概念（比如把「变量」比作贴了标签的盒子，'
        '把「循环」比作操场跑圈，把「函数」比作菜谱上的步骤）。\n'
        '2. 每一次解释概念之前，先说一句"你可以这样理解……"，然后给出类比。\n'
        '3. 语言要亲切、有耐心，像课间休息时坐在旁边的学长/学姐，'
        '不要说"显然""不难看出"这种话——对学生来说一切都很难。\n'
        '4. 学生卡住的时候，不要直接给答案。先问："你觉得这题让你完成了什么事情？"'
        '然后用苏格拉底式的追问引导他们自己发现解法。\n'
        '5. 如果学生犯了错，先肯定他们的努力（"你已经很接近了！"），'
        '再指出具体问题，最后给一个小提示。\n'
        '6. 每次回答控制在 150 字以内，简洁清晰，避免信息过载。\n'
        '7. 可以在合适的时候鼓励学生，比如"你已经学会变量赋值了，很厉害！"\n\n'
        '## 禁止事项\n'
        '- 绝不直接给出完整的代码答案。只能给思路、拆解步骤、解释概念。\n'
        '- 不使用"显然""简单""不言而喻"等让学生感到挫败的词语。\n'
        '- 不提及你是一个 AI 模型或机器人，你就是"小 P 老师"。\n'
        '- 不对编程之外的话题展开长篇讨论，可简短回应后引导回学习。\n'
    )

    if not context:
        return (
            f'{PERSONA}'
            '当前没有具体题目上下文，学生可能在做自由提问。'
            '请热情地回答他们的编程或信息科技相关问题。'
        )

    ctx_type = context.get('type', '')
    title = context.get('title', '')
    description = context.get('description', '')
    last_error = context.get('last_error', '')

    if ctx_type == 'ai_problem':
        return (
            f'{PERSONA}'
            f'## 当前题目\n'
            f'学生正在做的编程题：\n'
            f'**{title}**\n\n'
            f'### 题目描述\n'
            f'{description}\n\n'
            f'### 最近一次评测结果\n'
            f'{last_error if last_error else "暂无评测错误信息。"}\n\n'
            f'## 辅导策略\n'
            f'1. 先帮学生用大白话理解题目要求（"这道题其实就是让你……"）\n'
            f'2. 把任务拆成 2-3 个小步骤，每一步讲清楚后再讲下一步\n'
            f'3. 遇到新语法（比如 print、input、for），先用类比解释这个语法是什么\n'
            f'4. 学生如果问"怎么写"，只说思路和关键词法，不给完整代码\n'
            f'5. 如果题目涉及数学概念，用八年级学生能理解的数学知识解释\n'
            f'6. 如果存在最近一次评测结果，请优先结合测试点状态、实际输出和正确输出进行提示\n'
        )

    if ctx_type == 'info_quiz':
        return (
            f'{PERSONA}'
            f'## 当前小测\n'
            f'学生正在做信息科技课的小测：\n'
            f'**{title}**\n\n'
            f'### 小测信息\n'
            f'{description}\n\n'
            f'## 辅导策略\n'
            f'1. 学生可能会问某个概念，先用类比解释这个概念的含义\n'
            f'2. 可以举例说明，但不直接告诉学生这道题的正确答案\n'
            f'3. 引导学生回想相关知识："还记得之前学过……吗？"\n'
            f'4. 如果学生只是焦虑或不太确定，先安抚情绪再讲解知识\n'
        )

    return f'{PERSONA}当前没有具体题目上下文，请热情回答学生问题。'


def _sse_event(event, data):
    """构造一条 SSE 事件"""
    payload = json.dumps(data, ensure_ascii=False)
    return f'event: {event}\ndata: {payload}\n\n'


class ChatSendView(APIView):
    """POST /api/chat/send/ — SSE 流式代理到 MiniMax"""
    permission_classes = [IsStudent]

    def post(self, request):
        user = request.user
        # 正式小测作答期间前后端同时禁用 AI，不能靠直接调用接口绕过。
        from info_tech.models import QuizSubmission
        from info_tech.quiz_services import GRACE_SECONDS, settle_expired_attempts
        settle_expired_attempts()
        active_quiz = QuizSubmission.objects.filter(
            user=user,
            current_marker=True,
            status=QuizSubmission.STATUS_IN_PROGRESS,
        ).filter(
            Q(deadline_at__isnull=True)
            | Q(deadline_at__gte=timezone.now() - timedelta(seconds=GRACE_SECONDS))
        ).exists()
        if active_quiz:
            return Response({
                'error': '正式小测作答期间不能使用站内 AI 助手',
                'code': 'quiz_in_progress',
            }, status=403)

        message_text = (request.data.get('message', '') or '').strip()
        if not message_text:
            return Response({'error': '消息不能为空'}, status=400)

        session_id = request.data.get('session_id')
        context = request.data.get('context')

        # 获取或创建会话
        if session_id:
            try:
                session = ChatSession.objects.get(id=session_id, user=user)
            except ChatSession.DoesNotExist:
                session = ChatSession.objects.create(
                    user=user, title=message_text[:20]
                )
        else:
            session = ChatSession.objects.create(
                user=user, title=message_text[:20]
            )

        # 更新上下文快照
        if context:
            session.context_type = context.get('type', '')
            session.context_id = context.get('id', '')
            session.context_snapshot = context
            session.save(update_fields=[
                'context_type', 'context_id', 'context_snapshot'
            ])

        # 保存用户消息
        ChatMessage.objects.create(
            session=session, role='user', content=message_text
        )

        # 构建 messages 列表
        system_prompt = _build_system_prompt(context)
        messages = [{'role': 'system', 'content': system_prompt}]
        history = ChatMessage.objects.filter(session=session).order_by(
            'created_at'
        )
        for msg in history:
            messages.append({'role': msg.role, 'content': msg.content})

        def generate():
            """SSE 事件生成器：调用 MiniMax 流式 API 并逐块返回"""
            collected = ''
            try:
                _semaphore.acquire()

                client = OpenAI(
                    api_key=settings.MINIMAX_API_KEY,
                    base_url=settings.MINIMAX_API_BASE,
                )

                last_error = ''
                for attempt in range(3):
                    try:
                        stream = client.chat.completions.create(
                            model=settings.MINIMAX_MODEL,
                            messages=messages,
                            stream=True,
                        )
                        for chunk in stream:
                            if chunk.choices and chunk.choices[0].delta.content:
                                collected += chunk.choices[0].delta.content
                                yield _sse_event('token', {
                                    'content': chunk.choices[0].delta.content,
                                })
                        break  # 成功，跳出重试循环
                    except Exception as e:
                        last_error = str(e)
                        if '429' in last_error or 'rate' in last_error.lower():
                            if attempt < 2:
                                time.sleep(2 ** attempt)
                                continue
                        collected = ''
                        yield _sse_event('error', {
                            'error': 'AI 服务繁忙，请稍后重试',
                        })
                        return

                if collected:
                    # 保存 AI 回复到数据库
                    ChatMessage.objects.create(
                        session=session, role='assistant', content=collected
                    )
                    session.save()  # 更新 updated_at
                    yield _sse_event('done', {
                        'session_id': session.id,
                        'title': session.title,
                    })

            finally:
                _semaphore.release()

        response = StreamingHttpResponse(
            generate(),
            content_type='text/event-stream',
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


class ChatSessionListView(APIView):
    """GET /api/chat/sessions/ — 获取当前学生的会话列表"""
    permission_classes = [IsStudent]

    def get(self, request):
        user = request.user
        sessions = (
            ChatSession.objects.filter(user=user)
            .order_by('-updated_at')
            .values('id', 'title', 'context_type', 'created_at', 'updated_at')
        )

        result = []
        for s in sessions:
            msg_count = ChatMessage.objects.filter(session_id=s['id']).count()
            result.append({
                'id': s['id'],
                'title': s['title'],
                'context_type': s['context_type'],
                'created_at': s['created_at'].isoformat(),
                'updated_at': s['updated_at'].isoformat(),
                'message_count': msg_count,
            })

        return Response({'sessions': result})


class ChatSessionDetailView(APIView):
    """GET  /api/chat/sessions/<id>/messages/ — 获取会话消息
       DELETE /api/chat/sessions/<id>/ — 删除会话
    """
    permission_classes = [IsStudent]

    def get(self, request, pk):
        user = request.user
        try:
            session = ChatSession.objects.get(id=pk, user=user)
        except ChatSession.DoesNotExist:
            return Response({'error': '会话不存在'}, status=404)

        msgs = session.messages.values(
            'id', 'role', 'content', 'created_at'
        ).order_by('created_at')

        return Response({
            'session': {
                'id': session.id,
                'title': session.title,
                'context_type': session.context_type,
            },
            'messages': [
                {
                    'id': m['id'],
                    'role': m['role'],
                    'content': m['content'],
                    'created_at': m['created_at'].isoformat(),
                }
                for m in msgs
            ],
        })

    def delete(self, request, pk):
        user = request.user
        try:
            session = ChatSession.objects.get(id=pk, user=user)
        except ChatSession.DoesNotExist:
            return Response({'error': '会话不存在'}, status=404)

        session.delete()
        return Response({'ok': True})
