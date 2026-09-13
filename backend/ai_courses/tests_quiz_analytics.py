"""Step 10 teacher analytics API tests."""

from decimal import Decimal

from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from users.models import CustomUser

from .models import AIQuizAttempt, AIQuizAudience, AIQuizSession, Problem, Submission


class AIQuizAnalyticsAPITest(APITestCase):
    def setUp(self):
        self.teacher = CustomUser.objects.create_user(
            username='analytics_teacher', password='test', role='teacher', managed_grade='七年级',
        )
        self.other_teacher = CustomUser.objects.create_user(
            username='analytics_other_teacher', password='test', role='teacher', managed_grade='八年级',
        )
        numbers = ('10', '2', '01')
        self.students = [
            CustomUser.objects.create_user(
                username=f'analytics_student_{index}', password='test', role='student',
                display_name=name, grade='七年级', class_num=str(index),
                student_number=numbers[index - 1],
            )
            for index, name in enumerate(('甲', '乙', '丙'), 1)
        ]
        self.session = AIQuizSession.objects.create(
            title='快照统计小测', content_grade='七年级', created_by=self.teacher,
            status='open', blueprint_version=1,
            blueprint_json={'schema_version': 1, 'programming_items': [{
                'item_id': 'programming-item', 'source_problem_id': 'analytics_problem',
                'position': 1, 'points': '60.0', 'title': '冻结编程题标题',
            }]}, blueprint_hash='a' * 64,
        )
        AIQuizAudience.objects.create(
            session=self.session, scope_type='grade_all', grade='七年级',
            configured_by=self.teacher,
        )
        self.problem = Problem.objects.create(
            problem_id='analytics_problem', title='当前题库标题', description='公开题面',
            template_code='print(1)', course='ai', created_by=self.teacher,
        )
        snapshot = {
            'schema_version': 1,
            'session': {'title': '冻结标题', 'choice_points': '40.0'},
            'items': [{
                'item_id': 'choice-item', 'type': 'choice', 'position': 1,
                'source_question_id': 11, 'source_version': 3,
                'difficulty': 'easy', 'text': '冻结选择题',
                'options': {'A': '源B', 'B': '源A', 'C': '源D', 'D': '源C'},
                'source_option_by_display': {'A': 'B', 'B': 'A', 'C': 'D', 'D': 'C'},
                'correct_display_option': 'B',
            }, {
                'item_id': 'programming-item', 'type': 'programming', 'position': 2,
                'source_problem_id': self.problem.problem_id,
                'title': '冻结编程题标题', 'points': '60.0',
            }],
        }
        self.old_attempt = AIQuizAttempt.objects.create(
            user=self.students[0], session=self.session, status='superseded', attempt_no=1,
            current_marker=None, snapshot_json=snapshot, answers_json={'choice-item': 'A'},
            choice_score=Decimal('0'), programming_score=Decimal('90'), total_score=Decimal('90'),
            correct_count=0, choice_count=1, grade='七年级', class_num='1', student_number='01',
        )
        self.latest_attempt = AIQuizAttempt.objects.create(
            user=self.students[0], session=self.session, status='submitted', attempt_no=2,
            current_marker=True, snapshot_json=snapshot, answers_json={'choice-item': 'B'},
            choice_score=Decimal('40'), programming_score=Decimal('48'), total_score=Decimal('88'),
            correct_count=1, choice_count=1, grade='七年级', class_num='1', student_number='01',
        )
        self.in_progress = AIQuizAttempt.objects.create(
            user=self.students[1], session=self.session, status='in_progress', attempt_no=1,
            current_marker=True, snapshot_json=snapshot, answers_json={},
            grade='七年级', class_num='2', student_number='01',
        )
        Submission.objects.create(
            user=self.students[0], problem=self.problem, code='secret student code',
            score=80, status='wrong_answer', quiz_attempt=self.latest_attempt,
            quiz_item_id='programming-item',
        )
        self.token = Token.objects.create(user=self.teacher)

    def auth(self, user=None):
        if user is None:
            token = self.token
        else:
            token, _ = Token.objects.get_or_create(user=user)
        return {'HTTP_AUTHORIZATION': f'Token {token.key}'}

    def url(self, suffix):
        return f'/api/ai/admin/quizzes/{self.session.pk}/analytics/{suffix}'

    def test_overview_uses_expected_audience_and_latest_final_attempt(self):
        response = self.client.get(self.url('overview/'), **self.auth())
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['participation'], {
            'expected': 3, 'started': 2, 'not_started': 1,
            'in_progress': 1, 'settling': 0, 'submitted': 1, 'timed_out': 0,
        })
        self.assertEqual(response.data['scores']['average'], '88.0')
        self.assertEqual(response.data['scores']['choice_average_rate'], '100.0')

    def test_student_rows_are_paginated_filtered_and_show_latest_and_best(self):
        response = self.client.get(
            self.url('students/?page=1&page_size=1&class_num=1&q=甲'), **self.auth(),
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['pagination']['total'], 1)
        row = response.data['results'][0]
        self.assertEqual(row['latest_total_score'], '88.0')
        self.assertEqual(row['best_total_score'], '90.0')
        self.assertEqual(row['programming_items'][0]['best_score'], 80.0)
        self.assertNotIn('code', str(response.data).lower())
        self.assertNotIn('secret student code', str(response.data))

    def test_student_rows_filter_grade_sort_student_numbers_naturally_and_supply_lamps(self):
        response = self.client.get(
            self.url('students/?grade=七年级&page_size=20'), **self.auth(),
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            [row['student_number'] for row in response.data['results']],
            ['01', '2', '10'],
        )
        self.assertEqual(len(response.data['lamp_students']), 3)
        self.assertEqual(response.data['lamp_students'][0]['student_number'], '01')

    def test_attempt_history_is_paginated_and_has_code_free_item_summary(self):
        response = self.client.get(
            self.url(f'students/{self.students[0].pk}/attempts/?page_size=1'), **self.auth(),
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['pagination']['total'], 2)
        self.assertEqual(response.data['results'][0]['attempt_no'], 2)
        self.assertEqual(response.data['results'][0]['programming_items'][0]['best_score'], 80.0)
        self.assertNotIn('secret student code', str(response.data))

    def test_item_analysis_maps_shuffled_display_option_back_to_source_option(self):
        response = self.client.get(self.url('items/'), **self.auth())
        self.assertEqual(response.status_code, 200, response.data)
        choice = response.data['choice_items'][0]
        self.assertEqual(choice['text'], '冻结选择题')
        self.assertEqual(choice['correct_option'], 'A')
        self.assertEqual(choice['option_counts']['A'], 1)
        self.assertEqual(choice['options']['A'], '源A')
        programming = response.data['programming_items'][0]
        self.assertEqual(programming['title'], '冻结编程题标题')
        self.assertEqual(programming['average_best_score'], 80.0)

    def test_teacher_cannot_read_other_grade_quiz_analytics(self):
        response = self.client.get(self.url('overview/'), **self.auth(self.other_teacher))
        self.assertEqual(response.status_code, 404)
