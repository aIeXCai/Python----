"""Step 4 tests for AI quiz visibility, snapshots, recovery, and answer saves."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest import skipUnless
from unittest.mock import patch

from django.db import IntegrityError, connection, connections, transaction
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from users.models import CustomUser

from ..models import AIChoiceQuestion, AIQuizAttempt, AIQuizSession, AIUnit, Problem
from ..quizzes.attempt_services import start_or_resume_attempt
from ..quizzes.services import create_quiz, publish_quiz, update_quiz_audience


def teacher(username='attempt_teacher', grade='七年级'):
    return CustomUser.objects.create_user(
        username=username, password='test123', role='teacher', managed_grade=grade,
    )


def student(username, *, grade='七年级', class_num='1', number='01'):
    return CustomUser.objects.create_user(
        username=username,
        password='test123',
        role='student',
        grade=grade,
        class_num=class_num,
        student_number=number,
        display_name=username,
    )


def auth(user):
    return {'HTTP_AUTHORIZATION': f'Token {Token.objects.get_or_create(user=user)[0].key}'}


def build_published_choice_quiz(actor, section, *, audience=None, title='Step4 选择题小测'):
    values = {
        'title': title,
        'content_grade': section.grade,
        'choice_unit_ids': [section.pk],
        'choice_question_count': 2,
        'choice_difficulty_ratio': {'easy': 1, 'medium': 1, 'hard': 0},
        'choice_points': '100.0',
        'programming_items': [],
        'time_limit': 20,
        'audience': audience or [{
            'scope_type': 'grade_all', 'grade': section.grade,
        }],
    }
    session = create_quiz(actor=actor, values=values)
    return publish_quiz(actor=actor, session_id=session.pk, expected_version=1)


class AIQuizAttemptStep4APITest(APITestCase):
    def setUp(self):
        self.teacher = teacher()
        self.student = student('attempt_student')
        self.peer = student('attempt_peer', number='02')
        self.class_two = student('attempt_class_two', class_num='2', number='01')
        self.grade_eight = student(
            'attempt_grade_eight', grade='八年级', class_num='1', number='01',
        )
        self.root = AIUnit.objects.create(
            grade='七年级', name='attempt_root', display_name='AI 基础',
            created_by=self.teacher,
        )
        self.section = AIUnit.objects.create(
            grade='七年级', parent=self.root, name='attempt_section',
            display_name='智能基础', created_by=self.teacher,
        )
        for index, difficulty in enumerate(('easy', 'easy', 'medium', 'medium'), 1):
            AIChoiceQuestion.objects.create(
                unit=self.section,
                difficulty=difficulty,
                category='基础知识',
                text=f'冻结题干 {index}',
                option_a=f'正确选项 {index}',
                option_b=f'错误选项 B{index}',
                option_c=f'错误选项 C{index}',
                option_d=f'错误选项 D{index}',
                answer='A',
                explanation=f'秘密解析 {index}',
                created_by=self.teacher,
            )
        self.session = build_published_choice_quiz(self.teacher, self.section)

    def start(self, user=None, session=None):
        user = user or self.student
        session = session or self.session
        return self.client.post(
            f'/api/ai/quizzes/{session.pk}/attempt/', {}, format='json', **auth(user),
        )

    def test_list_filters_audience_and_reports_start_then_continue(self):
        listed = self.client.get('/api/ai/quizzes/', **auth(self.student))
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.data), 1)
        self.assertEqual(listed.data[0]['action'], 'start')
        self.assertEqual(listed.data[0]['choice_count'], 2)
        self.assertEqual(
            self.client.get('/api/ai/quizzes/', **auth(self.grade_eight)).data,
            [],
        )

        started = self.start()
        self.assertEqual(started.status_code, 201, started.data)
        continued = self.client.get('/api/ai/quizzes/', **auth(self.student))
        self.assertEqual(continued.data[0]['action'], 'continue')
        self.assertEqual(continued.data[0]['attempt_id'], started.data['attempt_id'])

    def test_list_reports_latest_and_historical_best_scores_separately(self):
        started = self.start().data
        current = AIQuizAttempt.objects.get(pk=started['attempt_id'])
        current.status = AIQuizAttempt.STATUS_SUBMITTED
        current.total_score = 70
        current.save(update_fields=['status', 'total_score'])
        AIQuizAttempt.objects.create(
            user=self.student, session=self.session, status=AIQuizAttempt.STATUS_SUPERSEDED,
            attempt_no=2, current_marker=None, snapshot_json=current.snapshot_json,
            total_score=90, grade='七年级', class_num='1', student_number='01',
        )
        listed = self.client.get('/api/ai/quizzes/', **auth(self.student))
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(float(listed.data[0]['latest_score']), 70.0)
        self.assertEqual(float(listed.data[0]['best_score']), 90.0)

    def test_start_response_is_allowlisted_and_uses_frozen_blueprint(self):
        original_texts = {
            item['text'] for item in self.session.blueprint_json['choice_pool']
        }
        question = AIChoiceQuestion.objects.first()
        question.text = '发布后被修改的题干'
        question.answer = 'D'
        question.explanation = '发布后被修改的解析'
        question.management_version += 1
        question.save(update_fields=['text', 'answer', 'explanation', 'management_version'])

        response = self.start()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(len(response.data['items']), 2)
        self.assertTrue({item['text'] for item in response.data['items']} <= original_texts)
        body = str(response.data)
        for forbidden in (
            'correct_display_option', 'source_option_by_display', 'source_question_id',
            'source_version', 'explanation', 'template_code', 'description',
            'test_snapshot',
        ):
            self.assertNotIn(forbidden, body)
        for item in response.data['items']:
            self.assertEqual(set(item['options']), set('ABCD'))

        attempt = AIQuizAttempt.objects.get(pk=response.data['attempt_id'])
        server_item = attempt.snapshot_json['items'][0]
        self.assertIn('correct_display_option', server_item)
        self.assertIn('source_option_by_display', server_item)
        self.assertIn('explanation', server_item)

    def test_start_and_get_are_idempotent_and_keep_snapshot_deadline(self):
        first = self.start()
        second = self.start()
        restored = self.client.get(
            f'/api/ai/quizzes/{self.session.pk}/attempt/', **auth(self.student),
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(first.data['attempt_id'], second.data['attempt_id'])
        self.assertEqual(first.data['attempt_id'], restored.data['attempt_id'])
        self.assertEqual(first.data['deadline_at'], second.data['deadline_at'])
        self.assertEqual(first.data['items'], restored.data['items'])
        self.assertEqual(AIQuizAttempt.objects.count(), 1)

    def test_save_full_answers_resume_and_revision_conflict(self):
        started = self.start().data
        first_id = started['items'][0]['item_id']
        second_id = started['items'][1]['item_id']
        url = f'/api/ai/quizzes/{self.session.pk}/attempt/answers/'
        saved = self.client.put(
            url,
            {
                'attempt_id': started['attempt_id'], 'revision': 0,
                'answers': {first_id: 'b', second_id: ''},
            },
            format='json', **auth(self.student),
        )
        self.assertEqual(saved.status_code, 200, saved.data)
        self.assertEqual(saved.data['revision'], 1)
        self.assertEqual(saved.data['saved_answers'], {first_id: 'B'})
        restored = self.client.get(
            f'/api/ai/quizzes/{self.session.pk}/attempt/', **auth(self.student),
        )
        self.assertEqual(restored.data['saved_answers'], {first_id: 'B'})

        stale = self.client.put(
            url,
            {
                'attempt_id': started['attempt_id'], 'revision': 0,
                'answers': {first_id: 'A'},
            },
            format='json', **auth(self.student),
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.data['code'], 'attempt_revision_conflict')
        self.assertEqual(stale.data['current_revision'], 1)
        attempt = AIQuizAttempt.objects.get(pk=started['attempt_id'])
        self.assertEqual(attempt.answers_json, {first_id: 'B'})

    def test_unknown_item_invalid_option_and_cross_user_are_atomic(self):
        started = self.start().data
        item_id = started['items'][0]['item_id']
        url = f'/api/ai/quizzes/{self.session.pk}/attempt/answers/'
        unknown = self.client.put(
            url,
            {
                'attempt_id': started['attempt_id'], 'revision': 0,
                'answers': {item_id: 'A', 'not-in-paper': 'B'},
            },
            format='json', **auth(self.student),
        )
        self.assertEqual(unknown.status_code, 400)
        self.assertEqual(unknown.data['code'], 'unknown_quiz_item')
        invalid = self.client.put(
            url,
            {
                'attempt_id': started['attempt_id'], 'revision': 0,
                'answers': {item_id: 'E'},
            },
            format='json', **auth(self.student),
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.data['code'], 'invalid_option')
        cross_user = self.client.put(
            url,
            {
                'attempt_id': started['attempt_id'], 'revision': 0,
                'answers': {item_id: 'A'},
            },
            format='json', **auth(self.peer),
        )
        self.assertEqual(cross_user.status_code, 404)
        attempt = AIQuizAttempt.objects.get(pk=started['attempt_id'])
        self.assertEqual(attempt.answers_json, {})
        self.assertEqual(attempt.answer_revision, 0)

    def test_scope_shrink_keeps_existing_attempt_but_blocks_new_student(self):
        started = self.start()
        self.assertEqual(started.status_code, 201)
        update_quiz_audience(
            actor=self.teacher,
            session_id=self.session.pk,
            expected_version=2,
            audience=[{
                'scope_type': 'class', 'grade': '七年级', 'class_num': '2',
            }],
        )
        resumed = self.start()
        self.assertEqual(resumed.status_code, 200, resumed.data)
        self.assertEqual(resumed.data['attempt_id'], started.data['attempt_id'])
        self.assertEqual(self.start(self.peer).status_code, 404)
        class_two = self.start(self.class_two)
        self.assertEqual(class_two.status_code, 201, class_two.data)

    def test_deadline_locks_attempt_before_returning_410(self):
        started = self.start().data
        item_id = started['items'][0]['item_id']
        attempt = AIQuizAttempt.objects.get(pk=started['attempt_id'])
        attempt.deadline_at = timezone.now() - timedelta(seconds=1)
        attempt.save(update_fields=['deadline_at'])
        response = self.client.put(
            f'/api/ai/quizzes/{self.session.pk}/attempt/answers/',
            {
                'attempt_id': attempt.pk, 'revision': 0,
                'answers': {item_id: 'A'},
            },
            format='json', **auth(self.student),
        )
        self.assertEqual(response.status_code, 410, response.data)
        self.assertEqual(response.data['code'], 'quiz_deadline_passed')
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, AIQuizAttempt.STATUS_SETTLING)
        self.assertEqual(attempt.final_reason, 'timed_out')
        self.assertIsNotNone(attempt.settlement_requested_at)
        self.assertEqual(attempt.answers_json, {})

    def test_database_allows_only_one_current_attempt(self):
        started = self.start().data
        attempt = AIQuizAttempt.objects.get(pk=started['attempt_id'])
        with self.assertRaises(IntegrityError), transaction.atomic():
            AIQuizAttempt.objects.create(
                user=self.student,
                session=self.session,
                status=AIQuizAttempt.STATUS_IN_PROGRESS,
                attempt_no=2,
                current_marker=True,
                snapshot_json=attempt.snapshot_json,
                grade=self.student.grade,
                class_num=self.student.class_num,
                student_number=self.student.student_number,
            )

    def test_closed_quiz_rejects_answer_writes(self):
        started = self.start().data
        item_id = started['items'][0]['item_id']
        self.session.status = AIQuizSession.STATUS_CLOSED
        self.session.closed_at = timezone.now()
        self.session.save(update_fields=['status', 'closed_at'])
        response = self.client.put(
            f'/api/ai/quizzes/{self.session.pk}/attempt/answers/',
            {
                'attempt_id': started['attempt_id'], 'revision': 0,
                'answers': {item_id: 'A'},
            },
            format='json', **auth(self.student),
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'quiz_not_open')

    @patch.object(Problem, 'get_test_cases', return_value=[{
        'number': 1, 'input': 'secret input', 'output': 'secret output',
    }])
    def test_mixed_snapshot_returns_only_programming_summary(self, _mock_cases):
        problem = Problem.objects.create(
            problem_id='step4_programming', title='快照编程题',
            description='不应在主响应出现的完整题干', template_code='# secret template',
            course='ai', grade_tag='七年级', unit=self.section,
            created_by=self.teacher,
        )
        session = create_quiz(actor=self.teacher, values={
            'title': 'Step4 混合小测',
            'content_grade': '七年级',
            'choice_unit_ids': [self.section.pk],
            'choice_question_count': 1,
            'choice_difficulty_ratio': {'easy': 1, 'medium': 0, 'hard': 0},
            'choice_points': '40.0',
            'programming_items': [{
                'problem_id': problem.problem_id, 'position': 1, 'points': '60.0',
            }],
            'time_limit': 20,
            'audience': [{'scope_type': 'grade_all', 'grade': '七年级'}],
        })
        session = publish_quiz(
            actor=self.teacher, session_id=session.pk, expected_version=1,
        )
        response = self.start(session=session)
        self.assertEqual(response.status_code, 201, response.data)
        programming = next(
            item for item in response.data['items'] if item['type'] == 'programming'
        )
        self.assertEqual(
            set(programming), {'item_id', 'type', 'position', 'title', 'points'},
        )
        attempt = AIQuizAttempt.objects.get(pk=response.data['attempt_id'])
        snapshot_item = next(
            item for item in attempt.snapshot_json['items']
            if item['type'] == 'programming'
        )
        self.assertNotIn('test_snapshot', snapshot_item)
        self.assertNotIn('secret input', str(attempt.snapshot_json))


@skipUnless(connection.vendor == 'mysql', 'MySQL/InnoDB concurrency integration test')
class AIQuizAttemptMySQLConcurrencyTest(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.teacher = teacher('attempt_concurrency_teacher')
        self.student = student('attempt_concurrency_student')
        root = AIUnit.objects.create(
            grade='七年级', name='concurrency_root', display_name='并发大单元',
            created_by=self.teacher,
        )
        section = AIUnit.objects.create(
            grade='七年级', parent=root, name='concurrency_section',
            display_name='并发小节', created_by=self.teacher,
        )
        for index, difficulty in enumerate(('easy', 'medium'), 1):
            AIChoiceQuestion.objects.create(
                unit=section, difficulty=difficulty, text=f'并发题 {index}',
                option_a='A', option_b='B', option_c='C', option_d='D',
                answer='A', created_by=self.teacher,
            )
        self.session = build_published_choice_quiz(self.teacher, section)

    def _start(self, _index):
        connections.close_all()
        user = CustomUser.objects.get(pk=self.student.pk)
        attempt, _created = start_or_resume_attempt(user, self.session.pk)
        attempt_id = attempt.pk
        connections.close_all()
        return attempt_id

    def test_concurrent_starts_return_one_current_attempt(self):
        with ThreadPoolExecutor(max_workers=10) as executor:
            attempt_ids = list(executor.map(self._start, range(10)))
        self.assertEqual(len(set(attempt_ids)), 1)
        self.assertEqual(AIQuizAttempt.objects.filter(
            user=self.student, session=self.session, current_marker=True,
        ).count(), 1)
