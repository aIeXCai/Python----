"""Step 3 tests for AI quiz drafts, validation, publication, and blueprint reuse."""

from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from execution.models import ExecutionTask
from users.models import CustomUser

from .models import (
    AIChoiceQuestion,
    AIQuizAttempt,
    AIQuizManagementAudit,
    AIQuizSession,
    AIUnit,
    Problem,
    Submission,
)
from .quiz_services import blueprint_digest


def make_teacher(username, grade='七年级', *, superuser=False):
    if superuser:
        return CustomUser.objects.create_superuser(username=username, password='test123')
    return CustomUser.objects.create_user(
        username=username,
        password='test123',
        role='teacher',
        managed_grade=grade,
    )


def auth(user):
    return {'HTTP_AUTHORIZATION': f'Token {Token.objects.create(user=user).key}'}


class AIQuizStep3APITest(APITestCase):
    def setUp(self):
        self.teacher = make_teacher('quiz_teacher')
        self.other_teacher = make_teacher('quiz_other', '八年级')
        self.admin = make_teacher('quiz_admin', superuser=True)
        self.teacher_auth = auth(self.teacher)
        self.other_auth = auth(self.other_teacher)
        self.admin_auth = auth(self.admin)
        self.root = AIUnit.objects.create(
            grade='七年级', name='root', display_name='AI 基础', created_by=self.teacher,
        )
        self.section = AIUnit.objects.create(
            grade='七年级', parent=self.root, name='section',
            display_name='机器学习入门', created_by=self.teacher,
        )
        self.other_root = AIUnit.objects.create(
            grade='八年级', name='other-root', display_name='八年级 AI',
            created_by=self.other_teacher,
        )
        self.other_section = AIUnit.objects.create(
            grade='八年级', parent=self.other_root, name='other-section',
            display_name='八年级小节', created_by=self.other_teacher,
        )
        CustomUser.objects.create_user(
            username='quiz_student', password='test123', role='student',
            grade='七年级', class_num='1', student_number='101', is_active=True,
        )

    def add_question(self, difficulty='easy', text='什么是人工智能？'):
        return AIChoiceQuestion.objects.create(
            unit=self.section,
            difficulty=difficulty,
            category='基础',
            text=text,
            option_a='机器表现出的智能能力',
            option_b='一种纸张',
            option_c='一种教室',
            option_d='一种铅笔',
            answer='A',
            explanation='A 是正确答案。',
            created_by=self.teacher,
        )

    def add_problem(self, problem_id='quiz_problem'):
        return Problem.objects.create(
            problem_id=problem_id,
            title='输出问候语',
            description='请输出 hello',
            difficulty='easy',
            grade_tag='七年级',
            unit=self.section,
            course='ai',
            template_code='print("hello")',
            created_by=self.teacher,
        )

    def create_quiz(self, **overrides):
        payload = {
            'title': 'AI 基础小测',
            'content_grade': '七年级',
            'choice_unit_ids': [],
            'choice_question_count': 0,
            'choice_difficulty_ratio': {'easy': 0, 'medium': 0, 'hard': 0},
            'choice_points': '0.0',
            'programming_items': [],
            'time_limit': 45,
            'audience': [
                {'scope_type': 'grade_all', 'grade': '七年级'},
            ],
        }
        payload.update(overrides)
        return self.client.post(
            '/api/ai/admin/quizzes/', payload, format='json', **self.teacher_auth,
        )

    def test_choice_quiz_crud_validate_publish_and_content_lock(self):
        self.add_question('easy', '题目一')
        self.add_question('medium', '题目二')
        created = self.create_quiz(
            choice_unit_ids=[self.section.pk],
            choice_question_count=2,
            choice_difficulty_ratio={'easy': 1, 'medium': 1, 'hard': 0},
            choice_points='100.0',
        )
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data['management_version'], 1)
        self.assertEqual(created.data['total_points'], '100.0')
        self.assertNotIn('blueprint_json', created.data)

        detail = self.client.get(
            f"/api/ai/admin/quizzes/{created.data['id']}/", **self.teacher_auth,
        )
        self.assertEqual(detail.status_code, 200)
        validated = self.client.post(
            f"/api/ai/admin/quizzes/{created.data['id']}/validate/",
            {'expected_version': 1}, format='json', **self.teacher_auth,
        )
        self.assertEqual(validated.status_code, 200, validated.data)
        self.assertTrue(validated.data['valid'])
        self.assertEqual(validated.data['choice_pool_count'], 2)

        published = self.client.post(
            f"/api/ai/admin/quizzes/{created.data['id']}/publish/",
            {'expected_version': 1}, format='json', **self.teacher_auth,
        )
        self.assertEqual(published.status_code, 200, published.data)
        self.assertEqual(published.data['status'], 'open')
        self.assertEqual(published.data['blueprint_version'], 1)
        self.assertEqual(len(published.data['blueprint_hash']), 64)
        session = AIQuizSession.objects.get(pk=created.data['id'])
        self.assertEqual(session.blueprint_hash, blueprint_digest(session.blueprint_json))
        self.assertEqual(len(session.blueprint_json['choice_pool']), 2)

        locked = self.client.patch(
            f"/api/ai/admin/quizzes/{session.pk}/",
            {'expected_version': 2, 'title': '不能修改'},
            format='json', **self.teacher_auth,
        )
        self.assertEqual(locked.status_code, 409)
        self.assertEqual(locked.data['code'], 'quiz_locked')

    def test_choice_pool_counts_multiple_questions_in_the_same_difficulty(self):
        self.add_question('easy', '同难度题目一')
        self.add_question('easy', '同难度题目二')
        created = self.create_quiz(
            choice_unit_ids=[self.section.pk],
            choice_question_count=2,
            choice_difficulty_ratio={'easy': 2, 'medium': 0, 'hard': 0},
            choice_points='100.0',
        )

        published = self.client.post(
            f"/api/ai/admin/quizzes/{created.data['id']}/publish/",
            {'expected_version': 1}, format='json', **self.teacher_auth,
        )

        self.assertEqual(published.status_code, 200, published.data)
        session = AIQuizSession.objects.get(pk=created.data['id'])
        self.assertEqual(len(session.blueprint_json['choice_pool']), 2)

    @patch.object(Problem, 'get_test_cases', return_value=[{
        'number': 1, 'input': '', 'output': 'hello',
    }])
    def test_programming_blueprint_is_frozen_and_reopen_reuses_it(self, _mock_cases):
        problem = self.add_problem()
        created = self.create_quiz(programming_items=[{
            'problem_id': problem.problem_id, 'position': 1, 'points': '100.0',
        }])
        self.assertEqual(created.status_code, 201, created.data)
        published = self.client.post(
            f"/api/ai/admin/quizzes/{created.data['id']}/publish/",
            {'expected_version': 1}, format='json', **self.teacher_auth,
        )
        self.assertEqual(published.status_code, 200, published.data)
        session = AIQuizSession.objects.get(pk=created.data['id'])
        original_blueprint = session.blueprint_json
        original_hash = session.blueprint_hash
        item = original_blueprint['programming_items'][0]
        self.assertEqual(item['source_problem_id'], problem.problem_id)
        self.assertEqual(item['test_snapshot']['cases'][0]['output'], 'hello')

        problem.title = '题库后来修改的标题'
        problem.management_version += 1
        problem.save(update_fields=['title', 'management_version'])
        closed = self.client.post(
            f'/api/ai/admin/quizzes/{session.pk}/close/',
            {'expected_version': 2}, format='json', **self.teacher_auth,
        )
        self.assertEqual(closed.status_code, 200, closed.data)
        reopened = self.client.post(
            f'/api/ai/admin/quizzes/{session.pk}/reopen/',
            {'expected_version': 3}, format='json', **self.teacher_auth,
        )
        self.assertEqual(reopened.status_code, 200, reopened.data)
        session.refresh_from_db()
        self.assertEqual(session.blueprint_json, original_blueprint)
        self.assertEqual(session.blueprint_hash, original_hash)

    def test_delete_quiz_removes_attempt_scores_submissions_and_executions(self):
        problem = self.add_problem('delete_quiz_problem')
        created = self.create_quiz(programming_items=[{
            'problem_id': problem.problem_id, 'position': 1, 'points': '100.0',
        }])
        session = AIQuizSession.objects.get(pk=created.data['id'])
        student = CustomUser.objects.get(username='quiz_student')
        attempt = AIQuizAttempt.objects.create(
            user=student, session=session, snapshot_json={},
            grade='七年级', class_num='1', student_number='101',
            total_score='80.0', choice_score='0.0', programming_score='80.0',
        )
        task = ExecutionTask.objects.create(
            user=student, problem=problem, quiz_attempt=attempt,
            quiz_item_id='programming:delete_quiz_problem', task_type='grade',
            status='succeeded', code='print(1)', snapshot_hash='hash', limits={},
            idempotency_key='delete-quiz-task', expires_at=timezone.now() + timedelta(hours=1),
        )
        submission = Submission.objects.create(
            user=student, problem=problem, code='print(1)', score=80,
            status='wrong_answer', execution_task=task, quiz_attempt=attempt,
            quiz_item_id='programming:delete_quiz_problem',
        )

        deleted = self.client.delete(
            f'/api/ai/admin/quizzes/{session.pk}/',
            {'expected_version': 1}, format='json', **self.teacher_auth,
        )
        self.assertEqual(deleted.status_code, 200, deleted.data)
        self.assertEqual(deleted.data['attempt_count'], 1)
        self.assertEqual(deleted.data['submission_count'], 1)
        self.assertEqual(deleted.data['execution_count'], 1)
        self.assertFalse(AIQuizSession.objects.filter(pk=session.pk).exists())
        self.assertFalse(AIQuizAttempt.objects.filter(pk=attempt.pk).exists())
        self.assertFalse(Submission.objects.filter(pk=submission.pk).exists())
        self.assertFalse(ExecutionTask.objects.filter(pk=task.pk).exists())
        self.assertTrue(AIQuizManagementAudit.objects.filter(
            event_type='quiz_delete', object_id=str(session.pk), outcome='success',
        ).exists())

    def test_publish_reports_pool_points_and_invalid_test_failures(self):
        self.add_question('easy')
        insufficient = self.create_quiz(
            title='题池不足',
            choice_unit_ids=[self.section.pk],
            choice_question_count=2,
            choice_difficulty_ratio={'easy': 2, 'medium': 0, 'hard': 0},
            choice_points='100.0',
        )
        response = self.client.post(
            f"/api/ai/admin/quizzes/{insufficient.data['id']}/publish/",
            {'expected_version': 1}, format='json', **self.teacher_auth,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'quiz_pool_insufficient')
        self.assertEqual(response.data['details']['easy']['available'], 1)

        bad_points = self.create_quiz(
            title='分值错误',
            choice_unit_ids=[self.section.pk],
            choice_question_count=1,
            choice_difficulty_ratio={'easy': 1, 'medium': 0, 'hard': 0},
            choice_points='90.0',
        )
        response = self.client.post(
            f"/api/ai/admin/quizzes/{bad_points.data['id']}/validate/",
            {'expected_version': 1}, format='json', **self.teacher_auth,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'quiz_points_invalid')

        problem = self.add_problem('invalid_tests')
        invalid_tests = self.create_quiz(
            title='无测试点', programming_items=[{
                'problem_id': problem.problem_id, 'position': 1, 'points': '100.0',
            }],
        )
        with patch.object(Problem, 'get_test_cases', return_value=[]):
            response = self.client.post(
                f"/api/ai/admin/quizzes/{invalid_tests.data['id']}/publish/",
                {'expected_version': 1}, format='json', **self.teacher_auth,
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'invalid_programming_problem')
        self.assertTrue(AIQuizManagementAudit.objects.filter(
            event_type='quiz_publish', outcome='failed',
            reason_code='invalid_programming_problem',
        ).exists())

    @patch.object(Problem, 'get_test_cases', return_value=[{
        'number': 1, 'input': '', 'output': 'hello',
    }])
    def test_copy_removes_blueprint_and_stale_version_conflicts(self, _mock_cases):
        problem = self.add_problem()
        created = self.create_quiz(programming_items=[{
            'problem_id': problem.problem_id, 'position': 1, 'points': '100.0',
        }])
        session_id = created.data['id']
        updated = self.client.patch(
            f'/api/ai/admin/quizzes/{session_id}/',
            {'expected_version': 1, 'title': '更新后的标题'},
            format='json', **self.teacher_auth,
        )
        self.assertEqual(updated.status_code, 200, updated.data)
        stale = self.client.patch(
            f'/api/ai/admin/quizzes/{session_id}/',
            {'expected_version': 1, 'title': '过期修改'},
            format='json', **self.teacher_auth,
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.data['management_version'], 2)
        published = self.client.post(
            f'/api/ai/admin/quizzes/{session_id}/publish/',
            {'expected_version': 2}, format='json', **self.teacher_auth,
        )
        self.assertEqual(published.status_code, 200, published.data)
        copied = self.client.post(
            f'/api/ai/admin/quizzes/{session_id}/copy/',
            {'title': '复用组卷'}, format='json', **self.teacher_auth,
        )
        self.assertEqual(copied.status_code, 201, copied.data)
        self.assertEqual(copied.data['status'], 'draft')
        self.assertEqual(copied.data['blueprint_version'], 0)
        self.assertEqual(copied.data['blueprint_hash'], '')
        self.assertEqual(copied.data['programming_items'][0]['problem_id'], problem.problem_id)

    def test_grade_and_audience_permissions_are_server_enforced(self):
        denied = self.client.post('/api/ai/admin/quizzes/', {
            'title': '跨年级小测', 'content_grade': '八年级',
        }, format='json', **self.teacher_auth)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.data['code'], 'teacher_grade_forbidden')

        invalid_scope = self.create_quiz(audience=[{
            'scope_type': 'all_school',
        }])
        self.assertEqual(invalid_scope.status_code, 403)
        self.assertEqual(invalid_scope.data['code'], 'quiz_scope_forbidden')

        admin_created = self.client.post('/api/ai/admin/quizzes/', {
            'title': '管理员跨年级范围',
            'content_grade': '七年级',
            'audience': [{'scope_type': 'all_school'}],
        }, format='json', **self.admin_auth)
        self.assertEqual(admin_created.status_code, 201, admin_created.data)
        hidden = self.client.get(
            f"/api/ai/admin/quizzes/{admin_created.data['id']}/", **self.other_auth,
        )
        self.assertEqual(hidden.status_code, 404)

    @patch.object(Problem, 'get_test_cases', return_value=[{
        'number': 1, 'input': '', 'output': 'hello',
    }])
    def test_mixed_quiz_and_published_audience_update(self, _mock_cases):
        self.add_question('easy')
        problem = self.add_problem('mixed_problem')
        created = self.create_quiz(
            title='混合小测',
            choice_unit_ids=[self.section.pk],
            choice_question_count=1,
            choice_difficulty_ratio={'easy': 1, 'medium': 0, 'hard': 0},
            choice_points='40.0',
            programming_items=[{
                'problem_id': problem.problem_id, 'position': 1, 'points': '60.0',
            }],
        )
        self.assertEqual(created.status_code, 201, created.data)
        published = self.client.post(
            f"/api/ai/admin/quizzes/{created.data['id']}/publish/",
            {'expected_version': 1}, format='json', **self.teacher_auth,
        )
        self.assertEqual(published.status_code, 200, published.data)
        self.assertEqual(published.data['total_question_count'], 2)

        audience = self.client.patch(
            f"/api/ai/admin/quizzes/{created.data['id']}/audience/",
            {
                'expected_version': 2,
                'audience': [{
                    'scope_type': 'class', 'grade': '七年级', 'class_num': '1',
                }],
            },
            format='json', **self.teacher_auth,
        )
        self.assertEqual(audience.status_code, 200, audience.data)
        self.assertEqual(audience.data['management_version'], 3)
        self.assertEqual(audience.data['audience'][0]['scope_type'], 'class')
        session = AIQuizSession.objects.get(pk=created.data['id'])
        self.assertEqual(len(session.blueprint_json['choice_pool']), 1)
        self.assertEqual(len(session.blueprint_json['programming_items']), 1)
        visible = self.client.get(
            '/api/ai/admin/quizzes/?grade=七年级&class_num=1',
            **self.teacher_auth,
        )
        hidden = self.client.get(
            '/api/ai/admin/quizzes/?grade=七年级&class_num=2',
            **self.teacher_auth,
        )
        self.assertIn(created.data['id'], [item['id'] for item in visible.data])
        self.assertNotIn(created.data['id'], [item['id'] for item in hidden.data])

    def test_blank_title_returns_validation_error(self):
        response = self.create_quiz(title='   ')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data['code'], 'quiz_configuration_invalid')
