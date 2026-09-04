from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from info_tech.models import QuizSession, QuizSubmission
from users.models import CustomUser


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
