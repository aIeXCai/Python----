from django.utils import timezone
from unittest.mock import patch
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from info_tech.models import QuizSession, QuizSubmission
from users.models import CustomUser
from ai_courses.models import AIQuizAttempt, AIQuizSession
from .models import ChatSession
from .views import _build_system_prompt


class QuizChatGuardTest(APITestCase):
    def test_active_formal_quiz_blocks_direct_chat_api(self):
        teacher = CustomUser.objects.create_user(
            username='chat-guard-teacher', password='test', role='teacher',
        )
        student = CustomUser.objects.create_user(
            username='chat-guard-student', password='test', role='student', grade='七年级',
            class_num='1', student_number='01',
        )
        session = QuizSession.objects.create(
            title='正式小测', created_by=teacher, num_questions=1,
            difficulty_ratio={'easy': 1}, status='open', visible_grades=['七年级'],
        )
        QuizSubmission.objects.create(
            user=student, session=session, grade='七年级',
            status='in_progress', snapshot_version=1,
            snapshot_json={'schema_version': 1, 'question_count': 1, 'questions': []},
            answers_json='{}', started_at=timezone.now(), submitted_at=None,
        )
        token = Token.objects.create(user=student)
        response = self.client.post(
            '/api/chat/send/', {'message': '答案是什么？'}, format='json',
            HTTP_AUTHORIZATION=f'Token {token.key}',
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['code'], 'quiz_in_progress')

    def test_active_ai_quiz_blocks_direct_choice_context(self):
        teacher = CustomUser.objects.create_user(
            username='ai-chat-teacher', password='test', role='teacher', managed_grade='七年级',
        )
        student = CustomUser.objects.create_user(
            username='ai-chat-student', password='test', role='student', grade='七年级',
            class_num='1', student_number='01',
        )
        session = AIQuizSession.objects.create(
            title='AI 正式小测', content_grade='七年级', created_by=teacher,
        )
        AIQuizAttempt.objects.create(
            user=student, session=session, status='in_progress', current_marker=True,
            snapshot_json={'schema_version': 1, 'items': []}, grade='七年级',
            class_num='1', student_number='01',
        )
        token = Token.objects.create(user=student)
        response = self.client.post(
            '/api/chat/send/',
            {'message': '这道选择题选什么？', 'context': {'type': 'ai_quiz_choice'}},
            format='json', HTTP_AUTHORIZATION=f'Token {token.key}',
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['code'], 'ai_quiz_choice_blocked')

    def test_programming_quiz_prompt_contains_public_code_context_without_answers(self):
        prompt = _build_system_prompt({
            'type': 'ai_quiz_programming', 'title': '输入输出',
            'description': '读入一个整数并输出', 'code': 'print(input())',
            'last_error': '实际输出不符',
        })
        self.assertIn('print(input())', prompt)
        self.assertIn('实际输出不符', prompt)
        self.assertNotIn('正确答案', prompt)
        self.assertNotIn('隐藏测试点', prompt.split('### 学生当前代码')[0])

    @patch('ai_courses.quizzes.execution_services.programming_item_payload')
    def test_programming_quiz_context_does_not_replace_chat_session_id(self, payload):
        teacher = CustomUser.objects.create_user(
            username='ai-chat-session-teacher', password='test', role='teacher', managed_grade='七年级',
        )
        student = CustomUser.objects.create_user(
            username='ai-chat-session-student', password='test', role='student', grade='七年级',
            class_num='1', student_number='02',
        )
        quiz = AIQuizSession.objects.create(
            title='编程小测', content_grade='七年级', created_by=teacher,
        )
        attempt = AIQuizAttempt.objects.create(
            user=student, session=quiz, status='in_progress', current_marker=True,
            snapshot_json={'schema_version': 1, 'items': []}, grade='七年级',
            class_num='1', student_number='02',
        )
        ChatSession.objects.create(user=student, title='占位会话')
        chat = ChatSession.objects.create(user=student, title='要继续的会话')
        payload.return_value = {
            'title': '安全题面', 'description': '只包含公开描述',
        }
        token = Token.objects.create(user=student)

        response = self.client.post(
            '/api/chat/send/', {
                'message': '帮我看看当前代码', 'session_id': chat.pk,
                'context': {
                    'type': 'ai_quiz_programming', 'session_id': quiz.pk,
                    'attempt_id': attempt.pk, 'id': 'programming-item-1',
                    'code': 'print(1)',
                },
            }, format='json', HTTP_AUTHORIZATION=f'Token {token.key}',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(chat.messages.get().content, '帮我看看当前代码')
        payload.assert_called_once_with(student, quiz.pk, 'programming-item-1')
