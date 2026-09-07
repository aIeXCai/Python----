"""AI 题目发布管理的权限、可见性与数据保留回归测试。"""

from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from users.models import CustomUser

from .models import (
    AUDIENCE_ALL_SCHOOL,
    AUDIENCE_CLASS,
    AUDIENCE_GRADE_ALL,
    Problem,
    ProblemAudience,
    ProblemManagementAudit,
    Submission,
)


def token_for(user):
    return Token.objects.get_or_create(user=user)[0].key


def auth(token):
    return {'HTTP_AUTHORIZATION': f'Token {token}'}


class ProblemPublicationApiTest(APITestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_superuser(
            username='alex_scope_admin', password='test123', role='teacher',
        )
        self.teacher7 = CustomUser.objects.create_user(
            username='scope_teacher7', password='test123', role='teacher',
            managed_grade='七年级',
        )
        self.teacher8 = CustomUser.objects.create_user(
            username='scope_teacher8', password='test123', role='teacher',
            managed_grade='八年级',
        )
        self.students = {}
        for grade, class_num in (('七年级', '1'), ('七年级', '2'), ('八年级', '1')):
            student = CustomUser.objects.create_user(
                username=f'scope_{grade}_{class_num}', password='test123',
                role='student', grade=grade, class_num=class_num,
                student_number=f'{class_num}01', managed_grade=grade,
            )
            self.students[(grade, class_num)] = student
        self.problem = Problem.objects.create(
            problem_id='scope_problem', title='范围测试', course='ai',
            created_by=self.teacher7,
        )

    def _student_get(self, grade, class_num, path='/api/ai/problems/'):
        return self.client.get(path, **auth(token_for(self.students[(grade, class_num)])))

    def _admin_patch(self, payload):
        return self.client.patch(
            '/api/ai/admin/problems/scope_problem/publication/',
            payload, format='json', **auth(token_for(self.admin)),
        )

    def test_problem_without_active_rule_is_unpublished(self):
        response = self._student_get('七年级', '1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        detail = self._student_get('七年级', '1', '/api/ai/problems/scope_problem/')
        self.assertEqual(detail.status_code, 404)

    def test_admin_can_publish_to_exact_grade_and_class_combinations(self):
        response = self._admin_patch({
            'expected_version': 1,
            'publishing_suspended': False,
            'all_school': False,
            'scopes': [
                {'grade': '七年级', 'visible': True, 'all_classes': False, 'classes': ['1']},
                {'grade': '八年级', 'visible': True, 'all_classes': True, 'classes': []},
            ],
        })
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(self._student_get('七年级', '1').data), 1)
        self.assertEqual(len(self._student_get('七年级', '2').data), 0)
        self.assertEqual(len(self._student_get('八年级', '1').data), 1)

    def test_admin_all_school_and_global_suspend(self):
        publish = self._admin_patch({
            'expected_version': 1,
            'publishing_suspended': False,
            'all_school': True,
            'scopes': [],
        })
        self.assertEqual(publish.status_code, 200, publish.data)
        self.assertEqual(len(self._student_get('七年级', '2').data), 1)

        suspended = self._admin_patch({
            'expected_version': publish.data['management_version'],
            'publishing_suspended': True,
            'all_school': True,
            'scopes': [],
        })
        self.assertEqual(suspended.status_code, 200, suspended.data)
        self.assertEqual(len(self._student_get('七年级', '1').data), 0)
        self.assertTrue(ProblemManagementAudit.objects.filter(
            problem_id=self.problem.problem_id,
            event_type='global_suspend', outcome='success',
        ).exists())

    def test_cancel_all_school_restores_previous_exact_scopes(self):
        exact = self._admin_patch({
            'expected_version': 1,
            'publishing_suspended': False,
            'all_school': False,
            'scopes': [
                {'grade': '七年级', 'visible': True, 'all_classes': False, 'classes': ['1']},
            ],
        })
        all_school = self._admin_patch({
            'expected_version': exact.data['management_version'],
            'publishing_suspended': False,
            'all_school': True,
            'scopes': exact.data['scopes'],
        })
        self.assertEqual(len(self._student_get('七年级', '2').data), 1)

        restored = self._admin_patch({
            'expected_version': all_school.data['management_version'],
            'publishing_suspended': False,
            'all_school': False,
            'scopes': all_school.data['scopes'],
        })
        self.assertEqual(restored.status_code, 200, restored.data)
        self.assertEqual(len(self._student_get('七年级', '1').data), 1)
        self.assertEqual(len(self._student_get('七年级', '2').data), 0)

    def test_teacher_only_changes_managed_grade(self):
        response = self.client.patch(
            '/api/ai/admin/problems/scope_problem/publication/',
            {
                'expected_version': 1,
                'visible': True,
                'all_classes': False,
                'classes': ['2'],
            }, format='json', **auth(token_for(self.teacher7)),
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['scopes'][0]['grade'], '七年级')
        self.assertEqual(len(self._student_get('七年级', '1').data), 0)
        self.assertEqual(len(self._student_get('七年级', '2').data), 1)
        self.assertFalse(ProblemAudience.objects.filter(
            problem=self.problem, grade='八年级', is_active=True,
        ).exists())

    def test_teacher_hide_and_reopen_restore_previous_class_selection(self):
        endpoint = '/api/ai/admin/problems/scope_problem/publication/'
        credentials = auth(token_for(self.teacher7))
        published = self.client.patch(endpoint, {
            'expected_version': 1, 'visible': True,
            'all_classes': False, 'classes': ['2'],
        }, format='json', **credentials)
        hidden = self.client.patch(endpoint, {
            'expected_version': published.data['management_version'],
            'visible': False, 'all_classes': False, 'classes': [],
        }, format='json', **credentials)
        self.assertEqual(hidden.status_code, 200, hidden.data)
        self.assertFalse(hidden.data['scopes'][0]['visible'])
        self.assertEqual(hidden.data['scopes'][0]['classes'], ['2'])

        reopened = self.client.patch(endpoint, {
            'expected_version': hidden.data['management_version'],
            'visible': True, 'all_classes': False,
            'classes': hidden.data['scopes'][0]['classes'],
        }, format='json', **credentials)
        self.assertEqual(reopened.status_code, 200, reopened.data)
        self.assertEqual(len(self._student_get('七年级', '2').data), 1)
        self.assertEqual(len(self._student_get('七年级', '1').data), 0)

    def test_teacher_forged_cross_grade_or_admin_payload_is_denied_and_audited(self):
        endpoint = '/api/ai/admin/problems/scope_problem/publication/'
        credentials = auth(token_for(self.teacher7))
        cross_grade = self.client.patch(endpoint, {
            'expected_version': 1, 'grade': '八年级',
            'visible': True, 'all_classes': True, 'classes': [],
        }, format='json', **credentials)
        self.assertEqual(cross_grade.status_code, 403)
        self.assertEqual(cross_grade.data['code'], 'teacher_grade_forbidden')

        forged_admin = self.client.patch(endpoint, {
            'expected_version': 1, 'visible': True,
            'all_classes': True, 'classes': [], 'all_school': True,
        }, format='json', **credentials)
        self.assertEqual(forged_admin.status_code, 403)
        self.assertTrue(ProblemManagementAudit.objects.filter(
            actor_user_id=self.teacher7.pk, problem_id=self.problem.problem_id,
            outcome='denied',
        ).exists())

    def test_teacher_cannot_override_admin_all_school_rule(self):
        ProblemAudience.objects.create(
            problem=self.problem, scope_type=AUDIENCE_ALL_SCHOOL, is_active=True,
            configured_by=self.admin,
        )
        response = self.client.patch(
            '/api/ai/admin/problems/scope_problem/publication/',
            {'expected_version': 1, 'visible': False, 'all_classes': False, 'classes': []},
            format='json', **auth(token_for(self.teacher7)),
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'all_school_managed_by_admin')
        self.assertTrue(ProblemManagementAudit.objects.filter(
            problem_id=self.problem.problem_id,
            outcome='conflict', reason_code='all_school_managed_by_admin',
        ).exists())

    def test_scope_update_rejects_stale_version(self):
        response = self._admin_patch({
            'expected_version': 99,
            'publishing_suspended': False,
            'all_school': True,
            'scopes': [],
        })
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'version_conflict')
        self.assertEqual(response.data['management_version'], 1)

    def test_class_options_are_real_classes_and_teacher_is_grade_scoped(self):
        response = self.client.get(
            '/api/ai/admin/problem-classes/?grade=七年级',
            **auth(token_for(self.teacher7)),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['classes'], ['1', '2'])
        forbidden = self.client.get(
            '/api/ai/admin/problem-classes/?grade=八年级',
            **auth(token_for(self.teacher7)),
        )
        self.assertEqual(forbidden.status_code, 403)

    def test_content_owner_and_admin_permissions(self):
        denied = self.client.patch(
            '/api/ai/admin/problems/scope_problem/',
            {'expected_version': 1, 'title': '越权修改'}, format='json',
            **auth(token_for(self.teacher8)),
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.data['code'], 'content_owner_required')
        self.problem.refresh_from_db()
        self.assertEqual(self.problem.title, '范围测试')

        changed = self.client.patch(
            '/api/ai/admin/problems/scope_problem/',
            {'expected_version': 1, 'title': '创建者已修改'}, format='json',
            **auth(token_for(self.teacher7)),
        )
        self.assertEqual(changed.status_code, 200, changed.data)
        self.assertEqual(changed.data['title'], '创建者已修改')

    def test_content_owner_can_set_grade_tag_and_invalid_tag_is_rejected(self):
        changed = self.client.patch(
            '/api/ai/admin/problems/scope_problem/',
            {'expected_version': 1, 'grade_tag': '八年级'}, format='json',
            **auth(token_for(self.teacher7)),
        )
        self.assertEqual(changed.status_code, 200, changed.data)
        self.assertEqual(changed.data['grade_tag'], '八年级')
        self.problem.refresh_from_db()
        self.assertEqual(self.problem.grade_tag, '八年级')

        invalid = self.client.patch(
            '/api/ai/admin/problems/scope_problem/',
            {'expected_version': changed.data['management_version'], 'grade_tag': '大学'},
            format='json', **auth(token_for(self.teacher7)),
        )
        self.assertEqual(invalid.status_code, 400)

    def test_archive_and_restore_preserve_submission(self):
        student = self.students[('七年级', '1')]
        submission = Submission.objects.create(
            user=student, problem=self.problem, code='print(1)', score=100,
            status='accepted',
        )
        archived = self.client.delete(
            '/api/ai/admin/problems/scope_problem/',
            {'expected_version': 1}, format='json', **auth(token_for(self.admin)),
        )
        self.assertEqual(archived.status_code, 200, archived.data)
        self.problem.refresh_from_db()
        self.assertIsNotNone(self.problem.archived_at)
        self.assertTrue(Submission.objects.filter(pk=submission.pk).exists())

        restored = self.client.post(
            '/api/ai/admin/problems/scope_problem/restore/',
            {'expected_version': self.problem.management_version}, format='json',
            **auth(token_for(self.admin)),
        )
        self.assertEqual(restored.status_code, 200, restored.data)
        self.problem.refresh_from_db()
        self.assertIsNone(self.problem.archived_at)
        self.assertTrue(self.problem.publishing_suspended)

    @override_settings(CODE_EXECUTION_ENABLED=True)
    def test_hidden_problem_cannot_be_submitted(self):
        response = self.client.post(
            '/api/ai/submissions/',
            {'problem_id': self.problem.problem_id, 'code': 'print(1)'}, format='json',
            **auth(token_for(self.students[('七年级', '1')])),
        )
        self.assertEqual(response.status_code, 404)

    def test_inactive_rules_do_not_publish(self):
        ProblemAudience.objects.create(
            problem=self.problem, scope_type=AUDIENCE_GRADE_ALL,
            grade='七年级', is_active=False,
        )
        ProblemAudience.objects.create(
            problem=self.problem, scope_type=AUDIENCE_CLASS,
            grade='七年级', class_num='1', is_active=False,
        )
        self.assertEqual(len(self._student_get('七年级', '1').data), 0)
