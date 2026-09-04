"""Stage 4 student quiz API contract and integrity tests."""
from datetime import timedelta

from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from users.models import CustomUser
from .models import Question, QuizSession, QuizSubmission, Unit


def make_teacher(grade='七年级', username='quiz_teacher'):
    return CustomUser.objects.create_user(
        username=username, password='test123', role='teacher',
        display_name='老师', managed_grade=grade,
    )


def make_student(grade='七年级', username='quiz_student'):
    student_number = '02' if username == 'other_student' else '01'
    return CustomUser.objects.create_user(
        username=username, password='test123', role='student',
        grade=grade, class_num='1', student_number=student_number, display_name='学生',
    )


def auth(user):
    return {'HTTP_AUTHORIZATION': f'Token {Token.objects.get_or_create(user=user)[0].key}'}


class Stage4QuizAPITest(APITestCase):
    def setUp(self):
        self.teacher = make_teacher()
        self.student = make_student()
        self.other_student = make_student(username='other_student')
        self.unit = Unit.objects.create(
            grade='七年级', name='stage4', display_name='阶段4单元', order=1,
        )
        for index in range(4):
            Question.objects.create(
                unit=self.unit,
                difficulty='easy',
                category='基础',
                text=f'题目{index}',
                answer='A',
                explanation=f'解析{index}',
                option_a=f'正确{index}',
                option_b=f'错误B{index}',
                option_c=f'错误C{index}',
                option_d=f'错误D{index}',
            )
        self.session = QuizSession.objects.create(
            title='可信小测',
            created_by=self.teacher,
            num_questions=4,
            difficulty_ratio={'easy': 4},
            time_limit=20,
            status=QuizSession.STATUS_OPEN,
            opened_at=timezone.now(),
            visible_grades=['七年级'],
        )
        self.session.units.add(self.unit)

    def start(self, student=None):
        student = student or self.student
        return self.client.post(
            f'/api/info/quizzes/{self.session.pk}/attempt/', {}, format='json', **auth(student),
        )

    def test_list_uses_student_grade_and_reports_action(self):
        response = self.client.get('/api/info/quizzes/', **auth(self.student))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['action'], 'start')

        wrong_grade = make_student('八年级', 'wrong_grade')
        response = self.client.get('/api/info/quizzes/', **auth(wrong_grade))
        self.assertEqual(response.data, [])

    def test_class_scope_filters_list_and_direct_start(self):
        class_two = CustomUser.objects.create_user(
            username='class_two_student', password='test123', role='student',
            grade='七年级', class_num='2', student_number='01', display_name='二班学生',
        )
        self.session.visible_classes = ['1']
        self.session.save(update_fields=['visible_classes'])

        self.assertEqual(len(self.client.get('/api/info/quizzes/', **auth(self.student)).data), 1)
        self.assertEqual(self.client.get('/api/info/quizzes/', **auth(class_two)).data, [])
        forbidden = self.start(class_two)
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(forbidden.data['code'], 'quiz_class_forbidden')

        self.session.visible_classes = []
        self.session.save(update_fields=['visible_classes'])
        self.assertEqual(len(self.client.get('/api/info/quizzes/', **auth(class_two)).data), 1)

    def test_only_student_role_can_start(self):
        response = self.client.post(
            f'/api/info/quizzes/{self.session.pk}/attempt/', {}, format='json', **auth(self.teacher),
        )
        self.assertEqual(response.status_code, 403)

    def test_start_response_does_not_leak_answers(self):
        response = self.start()
        self.assertEqual(response.status_code, 201)
        body = str(response.data)
        for forbidden in ('correct_option', 'correct_answer', 'explanation', 'source_question_id', 'shuffled_order'):
            self.assertNotIn(forbidden, body)
        self.assertEqual(len(response.data['questions']), 4)
        self.assertEqual(response.data['status'], 'in_progress')

    def test_start_is_idempotent_and_refresh_keeps_paper_and_deadline(self):
        first = self.start()
        second = self.start()
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data['attempt_id'], second.data['attempt_id'])
        self.assertEqual(first.data['deadline_at'], second.data['deadline_at'])
        self.assertEqual(first.data['questions'], second.data['questions'])
        self.assertEqual(QuizSubmission.objects.count(), 1)

    def test_insufficient_pool_does_not_create_partial_paper(self):
        self.session.num_questions = 5
        self.session.save(update_fields=['num_questions'])
        response = self.start()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'quiz_pool_insufficient')
        self.assertFalse(QuizSubmission.objects.exists())

    def test_save_and_resume_answers(self):
        started = self.start().data
        item_id = started['questions'][0]['item_id']
        response = self.client.put(
            f'/api/info/quizzes/{self.session.pk}/attempt/answers/',
            {'attempt_id': started['attempt_id'], 'revision': 0, 'answers': {item_id: 'B'}},
            format='json', **auth(self.student),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['revision'], 1)
        resumed = self.client.get(
            f'/api/info/quizzes/{self.session.pk}/attempt/', **auth(self.student),
        )
        self.assertEqual(resumed.data['saved_answers'], {item_id: 'B'})

    def test_old_revision_and_unknown_item_are_rejected_without_partial_write(self):
        started = self.start().data
        item_id = started['questions'][0]['item_id']
        url = f'/api/info/quizzes/{self.session.pk}/attempt/answers/'
        first = self.client.put(
            url, {'attempt_id': started['attempt_id'], 'revision': 0, 'answers': {item_id: 'A'}},
            format='json', **auth(self.student),
        )
        self.assertEqual(first.status_code, 200)
        stale = self.client.put(
            url, {'attempt_id': started['attempt_id'], 'revision': 0, 'answers': {item_id: 'B'}},
            format='json', **auth(self.student),
        )
        self.assertEqual(stale.status_code, 409)
        invalid = self.client.put(
            url, {'attempt_id': started['attempt_id'], 'revision': 1, 'answers': {'not-in-paper': 'A'}},
            format='json', **auth(self.student),
        )
        self.assertEqual(invalid.status_code, 400)
        attempt = QuizSubmission.objects.get(pk=started['attempt_id'])
        self.assertEqual(attempt.answers, {item_id: 'A'})

    def test_invalid_option_is_rejected_and_result_is_hidden_before_settlement(self):
        started = self.start().data
        item_id = started['questions'][0]['item_id']
        invalid = self.client.put(
            f'/api/info/quizzes/{self.session.pk}/attempt/answers/',
            {'attempt_id': started['attempt_id'], 'revision': 0, 'answers': {item_id: 'E'}},
            format='json', **auth(self.student),
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.data['code'], 'invalid_answers')
        result = self.client.get(
            f'/api/info/quizzes/{self.session.pk}/result/', **auth(self.student),
        )
        self.assertEqual(result.status_code, 409)
        self.assertEqual(result.data['code'], 'attempt_in_progress')

    def test_other_student_cannot_read_or_write_attempt(self):
        started = self.start().data
        item_id = started['questions'][0]['item_id']
        response = self.client.put(
            f'/api/info/quizzes/{self.session.pk}/attempt/answers/',
            {'attempt_id': started['attempt_id'], 'revision': 0, 'answers': {item_id: 'A'}},
            format='json', **auth(self.other_student),
        )
        self.assertEqual(response.status_code, 404)

    def test_fixed_denominator_and_immediate_wrong_answer_analysis(self):
        started = self.start().data
        attempt = QuizSubmission.objects.get(pk=started['attempt_id'])
        first = attempt.snapshot_json['questions'][0]
        response = self.client.post(
            f'/api/info/quizzes/{self.session.pk}/attempt/submit/',
            {
                'attempt_id': attempt.pk,
                'revision': 0,
                'answers': {first['item_id']: first['correct_option']},
            },
            format='json', **auth(self.student),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['score'], 25.0)
        self.assertEqual(response.data['total_count'], 4)

        result = self.client.get(
            f'/api/info/quizzes/{self.session.pk}/result/', **auth(self.student),
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data['score'], 25.0)
        self.assertEqual(len(result.data['question_results']), 3)
        for wrong in result.data['question_results']:
            self.assertFalse(wrong['is_correct'])
            self.assertIn(wrong['correct_answer'], 'ABCD')
            self.assertTrue(wrong['explanation'])
            self.assertIsNone(wrong['user_answer'])

    def test_question_edits_after_start_do_not_change_score_or_result(self):
        started = self.start().data
        attempt = QuizSubmission.objects.get(pk=started['attempt_id'])
        item = attempt.snapshot_json['questions'][0]
        source = Question.objects.get(pk=item['source_question_id'])
        original_text = item['text']
        source.text = '修改后的题干'
        source.answer = 'D'
        source.explanation = '修改后的解析'
        source.save()
        wrong_answer = next(letter for letter in 'ABCD' if letter != item['correct_option'])
        response = self.client.post(
            f'/api/info/quizzes/{self.session.pk}/attempt/submit/',
            {'attempt_id': attempt.pk, 'revision': 0, 'answers': {item['item_id']: wrong_answer}},
            format='json', **auth(self.student),
        )
        self.assertEqual(response.status_code, 200)
        result = self.client.get(f'/api/info/quizzes/{self.session.pk}/result/', **auth(self.student))
        wrong = next(row for row in result.data['question_results'] if row['item_id'] == item['item_id'])
        self.assertEqual(wrong['text'], original_text)
        self.assertEqual(wrong['explanation'], item['explanation'])

    def test_teacher_can_edit_open_quiz_without_changing_started_attempt(self):
        started = self.start().data
        original_questions = started['questions']
        original_deadline = started['deadline_at']

        updated = self.client.put(
            f'/api/admin/info/sessions/{self.session.pk}/',
            {
                'title': '修改后的小测',
                'units': [self.unit.pk],
                'num_questions': 2,
                'difficulty_ratio': {'easy': 2},
                'time_limit': 10,
                'visible_grades': ['七年级'],
                'visible_classes': ['2'],
            },
            format='json', **auth(self.teacher),
        )
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(updated.data['status'], 'open')
        self.assertEqual(updated.data['visible_classes'], ['2'])

        resumed = self.client.get(
            f'/api/info/quizzes/{self.session.pk}/attempt/', **auth(self.student),
        )
        self.assertEqual(resumed.status_code, 200)
        self.assertEqual(resumed.data['questions'], original_questions)
        self.assertEqual(resumed.data['deadline_at'], original_deadline)

        submitted = self.client.post(
            f'/api/info/quizzes/{self.session.pk}/attempt/submit/',
            {'attempt_id': started['attempt_id'], 'revision': 0, 'answers': {}},
            format='json', **auth(self.student),
        )
        self.assertEqual(submitted.status_code, 200)
        denied_new_attempt = self.start()
        self.assertEqual(denied_new_attempt.status_code, 403)
        self.assertEqual(denied_new_attempt.data['code'], 'quiz_class_forbidden')

    def test_submit_is_idempotent_and_next_start_creates_new_random_attempt(self):
        started = self.start().data
        payload = {'attempt_id': started['attempt_id'], 'revision': 0, 'answers': {}}
        url = f'/api/info/quizzes/{self.session.pk}/attempt/submit/'
        first = self.client.post(url, payload, format='json', **auth(self.student))
        second = self.client.post(url, payload, format='json', **auth(self.student))
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data['submission_id'], second.data['submission_id'])
        self.assertEqual(QuizSubmission.objects.count(), 1)

        listed = self.client.get('/api/info/quizzes/', **auth(self.student))
        self.assertEqual(listed.data[0]['action'], 'restart')
        self.assertEqual(listed.data[0]['score'], 0.0)
        restarted = self.start()
        self.assertEqual(restarted.status_code, 201)
        self.assertNotEqual(restarted.data['attempt_id'], started['attempt_id'])
        self.assertNotEqual(
            [item['item_id'] for item in restarted.data['questions']],
            [item['item_id'] for item in started['questions']],
        )
        old = QuizSubmission.objects.get(pk=started['attempt_id'])
        new = QuizSubmission.objects.get(pk=restarted.data['attempt_id'])
        self.assertIsNone(old.current_marker)
        self.assertTrue(new.current_marker)
        self.assertEqual(new.attempt_no, 2)

        # 新一轮尚未提交时，教师仍看到上一轮最近已完成成绩。
        stats = self.client.get(
            f'/api/admin/info/stats/submissions/?session_id={self.session.pk}',
            **auth(self.teacher),
        )
        self.assertEqual(stats.data['students'][0]['scores'], [0.0])

        current = QuizSubmission.objects.get(pk=restarted.data['attempt_id'])
        correct = {
            item['item_id']: item['correct_option']
            for item in current.snapshot_json['questions']
        }
        self.client.post(
            url,
            {'attempt_id': current.pk, 'revision': 0, 'answers': correct},
            format='json', **auth(self.student),
        )
        stats = self.client.get(
            f'/api/admin/info/stats/submissions/?session_id={self.session.pk}',
            **auth(self.teacher),
        )
        self.assertEqual(stats.data['students'][0]['scores'], [100.0])
        self.assertEqual(QuizSubmission.objects.count(), 2)

    def test_deadline_grace_accepts_submit_but_late_submit_uses_saved_draft(self):
        started = self.start().data
        attempt = QuizSubmission.objects.get(pk=started['attempt_id'])
        correct = {
            item['item_id']: item['correct_option']
            for item in attempt.snapshot_json['questions']
        }
        attempt.deadline_at = timezone.now() - timedelta(seconds=2)
        attempt.save(update_fields=['deadline_at'])
        response = self.client.post(
            f'/api/info/quizzes/{self.session.pk}/attempt/submit/',
            {'attempt_id': attempt.pk, 'revision': 0, 'answers': correct},
            format='json', **auth(self.student),
        )
        self.assertEqual(response.data['status'], 'submitted')
        self.assertEqual(response.data['score'], 100.0)

        self.client.post(
            f'/api/admin/info/sessions/{self.session.pk}/students/{self.student.pk}/reset/',
            {'reason': '网络故障'}, format='json', **auth(self.teacher),
        )
        started2 = self.start().data
        attempt2 = QuizSubmission.objects.get(pk=started2['attempt_id'])
        correct2 = {
            item['item_id']: item['correct_option']
            for item in attempt2.snapshot_json['questions']
        }
        attempt2.deadline_at = timezone.now() - timedelta(seconds=10)
        attempt2.save(update_fields=['deadline_at'])
        late = self.client.post(
            f'/api/info/quizzes/{self.session.pk}/attempt/submit/',
            {'attempt_id': attempt2.pk, 'revision': 0, 'answers': correct2},
            format='json', **auth(self.student),
        )
        self.assertEqual(late.data['status'], 'timed_out')
        self.assertEqual(late.data['score'], 0.0)

    def test_teacher_reset_keeps_history_and_allows_new_attempt(self):
        started = self.start().data
        self.client.post(
            f'/api/info/quizzes/{self.session.pk}/attempt/submit/',
            {'attempt_id': started['attempt_id'], 'revision': 0, 'answers': {}},
            format='json', **auth(self.student),
        )
        response = self.client.post(
            f'/api/admin/info/sessions/{self.session.pk}/students/{self.student.pk}/reset/',
            {'reason': '电脑故障'}, format='json', **auth(self.teacher),
        )
        self.assertEqual(response.status_code, 200)
        old = QuizSubmission.objects.get(pk=started['attempt_id'])
        self.assertEqual(old.status, 'reset')
        self.assertIsNone(old.current_marker)
        self.assertEqual(old.reset_by, self.teacher)
        new = self.start()
        self.assertEqual(new.status_code, 201)
        self.assertEqual(QuizSubmission.objects.get(pk=new.data['attempt_id']).attempt_no, 2)

    def test_closing_quiz_settles_saved_draft(self):
        self.session.visible_classes = ['1']
        self.session.save(update_fields=['visible_classes'])
        started = self.start().data
        attempt = QuizSubmission.objects.get(pk=started['attempt_id'])
        item = attempt.snapshot_json['questions'][0]
        self.client.put(
            f'/api/info/quizzes/{self.session.pk}/attempt/answers/',
            {'attempt_id': attempt.pk, 'revision': 0, 'answers': {item['item_id']: item['correct_option']}},
            format='json', **auth(self.student),
        )
        response = self.client.patch(
            f'/api/admin/info/sessions/{self.session.pk}/status/',
            {'status': 'closed'}, format='json', **auth(self.teacher),
        )
        self.assertEqual(response.status_code, 200)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, 'timed_out')
        self.assertEqual(attempt.score, 25.0)
        result = self.client.get(f'/api/info/quizzes/{self.session.pk}/result/', **auth(self.student))
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.data['can_retry'])

        # 关闭后学生列表隐藏；重新开放后再次出现并可生成新一轮作答。
        hidden = self.client.get('/api/info/quizzes/', **auth(self.student))
        self.assertEqual(hidden.data, [])
        reopened = self.client.patch(
            f'/api/admin/info/sessions/{self.session.pk}/status/',
            {'status': 'open', 'visible_classes': ['2']}, format='json', **auth(self.teacher),
        )
        self.assertEqual(reopened.status_code, 200)
        self.assertEqual(reopened.data['status'], 'open')
        self.assertEqual(reopened.data['visible_classes'], ['1'])
        visible = self.client.get('/api/info/quizzes/', **auth(self.student))
        self.assertEqual(visible.data[0]['action'], 'restart')
        restarted = self.start()
        self.assertEqual(restarted.status_code, 201)
        self.assertEqual(
            QuizSubmission.objects.get(pk=restarted.data['attempt_id']).attempt_no,
            2,
        )

    def test_other_teacher_cannot_manage_session_but_owner_can_edit_open_session(self):
        other_teacher = make_teacher('八年级', 'other_teacher')
        forbidden = self.client.patch(
            f'/api/admin/info/sessions/{self.session.pk}/status/',
            {'status': 'closed'}, format='json', **auth(other_teacher),
        )
        self.assertEqual(forbidden.status_code, 404)

        update = self.client.put(
            f'/api/admin/info/sessions/{self.session.pk}/',
            {
                'title': '试图修改', 'units': [self.unit.pk], 'num_questions': 1,
                'difficulty_ratio': {'easy': 1}, 'time_limit': 10,
                'visible_grades': ['七年级'],
            },
            format='json', **auth(self.teacher),
        )
        self.assertEqual(update.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.title, '试图修改')

    def test_legacy_submit_protocol_is_gone(self):
        response = self.client.post(
            f'/api/info/quizzes/{self.session.pk}/submit/', {'answers': {}},
            format='json', **auth(self.student),
        )
        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.data['code'], 'quiz_api_upgraded')
