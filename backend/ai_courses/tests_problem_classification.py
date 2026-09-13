"""Step 2 tests for programming-problem classification and quiz eligibility."""

import os
import tempfile
from unittest.mock import patch

from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from users.models import CustomUser

from .models import AIUnit, Problem


def make_teacher(username, grade='七年级'):
    return CustomUser.objects.create_user(
        username=username, password='test123', role='teacher', managed_grade=grade,
    )


def auth(user):
    return {'HTTP_AUTHORIZATION': f'Token {Token.objects.create(user=user).key}'}


class ProgrammingProblemClassificationAPITest(APITestCase):
    def setUp(self):
        self.owner = make_teacher('classification_owner')
        self.other_grade = make_teacher('classification_other', '八年级')
        self.owner_auth = auth(self.owner)
        self.other_auth = auth(self.other_grade)
        self.root = AIUnit.objects.create(
            grade='七年级', name='ai_root', display_name='AI 基础', created_by=self.owner,
        )
        self.section = AIUnit.objects.create(
            grade='七年级', parent=self.root, name='ai_section',
            display_name='认识人工智能', created_by=self.owner,
        )
        self.other_root = AIUnit.objects.create(
            grade='八年级', name='other_root', display_name='八年级 AI',
            created_by=self.other_grade,
        )
        self.other_section = AIUnit.objects.create(
            grade='八年级', parent=self.other_root, name='other_section',
            display_name='八年级小节', created_by=self.other_grade,
        )
        self.problem = Problem.objects.create(
            problem_id='classify_me', title='待归类题', description='有效题干',
            course='ai', created_by=self.owner,
        )

    @patch.object(Problem, 'get_test_count', return_value=2)
    def test_assigning_leaf_syncs_grade_and_returns_unit_metadata(self, _mock_count):
        response = self.client.patch(
            '/api/ai/admin/problems/classify_me/',
            {'expected_version': 1, 'unit': self.section.pk},
            format='json', **self.owner_auth,
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['unit'], self.section.pk)
        self.assertEqual(response.data['unit_name'], '认识人工智能')
        self.assertEqual(response.data['big_unit_id'], self.root.pk)
        self.assertEqual(response.data['big_unit_name'], 'AI 基础')
        self.assertEqual(response.data['unit_grade'], '七年级')
        self.assertEqual(response.data['grade_tag'], '七年级')
        self.assertTrue(response.data['quiz_usable'])
        self.assertEqual(response.data['quiz_unusable_reasons'], [])
        self.problem.refresh_from_db()
        self.assertEqual(self.problem.unit_id, self.section.pk)
        self.assertEqual(self.problem.grade_tag, '七年级')

    def test_rejects_root_archived_cross_grade_and_conflicting_grade(self):
        root_response = self.client.patch(
            '/api/ai/admin/problems/classify_me/',
            {'expected_version': 1, 'unit': self.root.pk},
            format='json', **self.owner_auth,
        )
        self.assertEqual(root_response.status_code, 400)
        self.assertEqual(root_response.data['code'], 'invalid_problem_unit')

        cross_grade = self.client.patch(
            '/api/ai/admin/problems/classify_me/',
            {'expected_version': 1, 'unit': self.other_section.pk},
            format='json', **self.owner_auth,
        )
        self.assertEqual(cross_grade.status_code, 403)
        self.assertEqual(cross_grade.data['code'], 'teacher_grade_forbidden')

        conflict = self.client.patch(
            '/api/ai/admin/problems/classify_me/',
            {'expected_version': 1, 'unit': self.section.pk, 'grade_tag': '八年级'},
            format='json', **self.owner_auth,
        )
        self.assertEqual(conflict.status_code, 400)
        self.assertEqual(conflict.data['code'], 'problem_unit_grade_conflict')

        self.section.archive()
        archived = self.client.patch(
            '/api/ai/admin/problems/classify_me/',
            {'expected_version': 1, 'unit': self.section.pk},
            format='json', **self.owner_auth,
        )
        self.assertEqual(archived.status_code, 400)
        self.assertEqual(archived.data['code'], 'invalid_problem_unit')

    def test_existing_classification_blocks_independent_grade_change_and_can_clear_unit(self):
        self.problem.unit = self.section
        self.problem.grade_tag = '七年级'
        self.problem.save(update_fields=['unit', 'grade_tag'])
        conflict = self.client.patch(
            '/api/ai/admin/problems/classify_me/',
            {'expected_version': 1, 'grade_tag': '八年级'},
            format='json', **self.owner_auth,
        )
        self.assertEqual(conflict.status_code, 400)
        self.assertEqual(conflict.data['code'], 'problem_unit_grade_conflict')

        cleared = self.client.patch(
            '/api/ai/admin/problems/classify_me/',
            {'expected_version': 1, 'unit': None},
            format='json', **self.owner_auth,
        )
        self.assertEqual(cleared.status_code, 200, cleared.data)
        self.assertIsNone(cleared.data['unit'])
        self.assertEqual(cleared.data['grade_tag'], '七年级')

    @patch('ai_courses.problem_eligibility.cached_test_count')
    def test_list_filters_by_grade_unit_search_and_usable(self, mock_count):
        self.problem.unit = self.section
        self.problem.grade_tag = '七年级'
        self.problem.save(update_fields=['unit', 'grade_tag'])
        Problem.objects.create(
            problem_id='unclassified', title='未分类', description='有效题干',
            grade_tag='七年级', course='ai', created_by=self.owner,
        )
        Problem.objects.create(
            problem_id='no_tests', title='没有测试点', description='有效题干',
            grade_tag='七年级', unit=self.section, course='ai', created_by=self.owner,
        )
        mock_count.side_effect = lambda problem: 0 if problem.problem_id == 'no_tests' else 1

        unit_response = self.client.get(
            f'/api/ai/admin/problems/?unit={self.section.pk}', **self.owner_auth,
        )
        self.assertEqual(unit_response.status_code, 200)
        self.assertEqual(
            {item['problem_id'] for item in unit_response.data},
            {'classify_me', 'no_tests'},
        )
        unclassified = self.client.get(
            '/api/ai/admin/problems/?unit=unclassified', **self.owner_auth,
        )
        self.assertEqual([item['problem_id'] for item in unclassified.data], ['unclassified'])
        searched = self.client.get(
            '/api/ai/admin/problems/?q=待归类', **self.owner_auth,
        )
        self.assertEqual([item['problem_id'] for item in searched.data], ['classify_me'])
        usable = self.client.get('/api/ai/admin/problems/?usable=1', **self.owner_auth)
        self.assertEqual(
            {item['problem_id'] for item in usable.data},
            {'classify_me'},
        )
        grade_forbidden = self.client.get(
            '/api/ai/admin/problems/?grade=八年级', **self.owner_auth,
        )
        self.assertEqual(grade_forbidden.status_code, 403)

    @patch.object(Problem, 'get_test_count', return_value=0)
    def test_unusable_reasons_are_stable(self, _mock_count):
        response = self.client.get('/api/ai/admin/problems/', **self.owner_auth)
        self.assertEqual(response.status_code, 200)
        item = response.data[0]
        self.assertFalse(item['quiz_usable'])
        self.assertEqual(
            [reason['code'] for reason in item['quiz_unusable_reasons']],
            ['unit_missing', 'test_cases_missing'],
        )

    def test_disk_sync_preserves_manual_unit_and_grade(self):
        problem = Problem.objects.create(
            problem_id='problem_sync_preserve', title='旧标题', description='旧题干',
            grade_tag='七年级', unit=self.section, course='ai', created_by=self.owner,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            problem_dir = os.path.join(temp_dir, 'ai', problem.problem_id)
            os.makedirs(problem_dir)
            with open(os.path.join(problem_dir, 'description.txt'), 'w', encoding='utf-8') as file:
                file.write('磁盘更新后的题干')
            with patch('ai_courses.models.settings') as mock_settings:
                mock_settings.PROBLEMS_DIR = temp_dir
                result = Problem.sync_from_disk(actor=self.owner)

        self.assertEqual(result.failed, [], result.as_dict())
        self.assertEqual(result.updated, [problem.problem_id], result.as_dict())
        problem.refresh_from_db()
        self.assertEqual(problem.unit_id, self.section.pk)
        self.assertEqual(problem.grade_tag, '七年级')
        self.assertEqual(problem.description, '磁盘更新后的题干')
