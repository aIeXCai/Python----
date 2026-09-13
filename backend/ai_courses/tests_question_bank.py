"""Step 1 tests for the AI unit and choice-question bank."""

from django.core.exceptions import ValidationError
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from users.models import CustomUser

from .models import AIChoiceQuestion, AIUnit, Problem


def teacher(username, grade='七年级'):
    return CustomUser.objects.create_user(
        username=username,
        password='test123',
        role='teacher',
        managed_grade=grade,
    )


def auth(user):
    return {'HTTP_AUTHORIZATION': f'Token {Token.objects.create(user=user).key}'}


def question_payload(unit_id, **overrides):
    values = {
        'unit': unit_id,
        'difficulty': 'easy',
        'category': '人工智能基础',
        'text': '以下哪一项属于人工智能应用？',
        'option_a': '图像识别',
        'option_b': '手工打字',
        'option_c': '纸张装订',
        'option_d': '机械铅笔',
        'answer': 'A',
        'explanation': '图像识别是典型的 AI 应用。',
    }
    values.update(overrides)
    return values


def model_question(unit, **overrides):
    values = question_payload(unit.pk, **overrides)
    values.pop('unit')
    return AIChoiceQuestion(unit=unit, **values)


class AIQuestionBankModelTest(APITestCase):
    def setUp(self):
        self.owner = teacher('model_owner')
        self.root = AIUnit.objects.create(
            grade='七年级', name='u1', display_name='第一单元', created_by=self.owner,
        )
        self.section = AIUnit.objects.create(
            grade='七年级', parent=self.root, name='s1', display_name='第一节',
            created_by=self.owner,
        )

    def test_unit_rejects_third_level_and_cross_grade_parent(self):
        third = AIUnit(
            grade='七年级', parent=self.section, name='third', display_name='第三级',
        )
        with self.assertRaises(ValidationError):
            third.full_clean()
        cross_grade = AIUnit(
            grade='八年级', parent=self.root, name='cross', display_name='跨年级',
        )
        with self.assertRaises(ValidationError):
            cross_grade.full_clean()

    def test_choice_question_requires_active_leaf_and_valid_content(self):
        root_question = model_question(self.root, created_by=self.owner)
        with self.assertRaises(ValidationError):
            root_question.full_clean()
        blank_question = model_question(self.section, option_d='  ', created_by=self.owner)
        with self.assertRaises(ValidationError):
            blank_question.full_clean()
        self.root.archive()
        archived_question = model_question(self.section, created_by=self.owner)
        with self.assertRaises(ValidationError):
            archived_question.full_clean()

    def test_problem_unit_validation_keeps_legacy_unit_optional(self):
        legacy = Problem(problem_id='legacy-unclassified', course='ai')
        legacy.full_clean()
        problem = Problem(
            problem_id='classified', course='ai', unit=self.section, grade_tag='八年级',
        )
        with self.assertRaises(ValidationError):
            problem.full_clean()


class AIUnitAPITest(APITestCase):
    def setUp(self):
        self.teacher = teacher('unit_teacher')
        self.other_grade_teacher = teacher('unit_other_grade', '八年级')
        self.teacher_auth = auth(self.teacher)
        self.other_auth = auth(self.other_grade_teacher)

    def test_unit_crud_hierarchy_duplicate_and_grade_scope(self):
        response = self.client.post('/api/ai/admin/units/', {
            'grade': '七年级', 'name': 'ai_intro', 'display_name': 'AI 入门', 'order': 1,
        }, format='json', **self.teacher_auth)
        self.assertEqual(response.status_code, 201, response.data)
        root_id = response.data['id']
        section = self.client.post('/api/ai/admin/units/', {
            'grade': '七年级', 'parent': root_id,
            'name': 'history', 'display_name': 'AI 发展史', 'order': 1,
        }, format='json', **self.teacher_auth)
        self.assertEqual(section.status_code, 201, section.data)

        duplicate = self.client.post('/api/ai/admin/units/', {
            'grade': '七年级', 'parent': root_id,
            'name': 'history', 'display_name': '重复小节',
        }, format='json', **self.teacher_auth)
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.data['code'], 'duplicate_unit_name')

        patched = self.client.patch(
            f"/api/ai/admin/units/{section.data['id']}/",
            {'display_name': 'AI 发展历程'}, format='json', **self.teacher_auth,
        )
        self.assertEqual(patched.status_code, 200, patched.data)
        self.assertEqual(patched.data['display_name'], 'AI 发展历程')

        denied = self.client.post('/api/ai/admin/units/', {
            'grade': '八年级', 'name': 'forbidden', 'display_name': '越权',
        }, format='json', **self.teacher_auth)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.data['code'], 'teacher_grade_forbidden')

        other_list = self.client.get('/api/ai/admin/units/', **self.other_auth)
        self.assertEqual(other_list.status_code, 200)
        self.assertEqual(other_list.data, [])

        listed = self.client.get('/api/ai/admin/units/?grade=七年级', **self.teacher_auth)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.data), 1)
        self.assertEqual(len(listed.data[0]['sections']), 1)

    def test_archive_root_effectively_hides_children_and_restore(self):
        root = AIUnit.objects.create(
            grade='七年级', name='root', display_name='大单元', created_by=self.teacher,
        )
        section = AIUnit.objects.create(
            grade='七年级', parent=root, name='section', display_name='小节',
            created_by=self.teacher,
        )
        archived = self.client.delete(
            f'/api/ai/admin/units/{root.pk}/', format='json', **self.teacher_auth,
        )
        self.assertEqual(archived.status_code, 200)
        self.assertIsNotNone(archived.data['archived_at'])
        active_list = self.client.get('/api/ai/admin/units/', **self.teacher_auth)
        self.assertEqual(active_list.data, [])
        included = self.client.get('/api/ai/admin/units/?include_archived=1', **self.teacher_auth)
        self.assertEqual(len(included.data), 1)
        self.assertTrue(included.data[0]['sections'][0]['effectively_archived'])

        self.client.delete(
            f'/api/ai/admin/units/{section.pk}/', format='json', **self.teacher_auth,
        )
        blocked = self.client.post(
            f'/api/ai/admin/units/{section.pk}/restore/', {}, format='json', **self.teacher_auth,
        )
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.data['code'], 'parent_unit_archived')
        restored = self.client.post(
            f'/api/ai/admin/units/{root.pk}/restore/', {}, format='json', **self.teacher_auth,
        )
        self.assertEqual(restored.status_code, 200)

    def test_permanently_delete_empty_section_then_empty_root(self):
        root = AIUnit.objects.create(
            grade='七年级', name='empty_root', display_name='输入输出',
            created_by=self.teacher,
        )
        section = AIUnit.objects.create(
            grade='七年级', parent=root, name='empty_section', display_name='空小节',
            created_by=self.teacher,
        )
        listed = self.client.get('/api/ai/admin/units/', **self.teacher_auth)
        self.assertFalse(listed.data[0]['can_delete'])
        self.assertTrue(listed.data[0]['sections'][0]['can_delete'])

        blocked = self.client.delete(
            f'/api/ai/admin/units/{root.pk}/permanent/', **self.teacher_auth,
        )
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.data['code'], 'unit_not_empty')

        section.archive()
        active_list = self.client.get('/api/ai/admin/units/', **self.teacher_auth)
        self.assertFalse(active_list.data[0]['can_delete'])

        deleted_section = self.client.delete(
            f'/api/ai/admin/units/{section.pk}/permanent/', **self.teacher_auth,
        )
        self.assertEqual(deleted_section.status_code, 204)
        deleted_root = self.client.delete(
            f'/api/ai/admin/units/{root.pk}/permanent/', **self.teacher_auth,
        )
        self.assertEqual(deleted_root.status_code, 204)
        self.assertFalse(AIUnit.objects.filter(pk__in=[root.pk, section.pk]).exists())


class AIChoiceQuestionAPITest(APITestCase):
    def setUp(self):
        self.owner = teacher('question_owner')
        self.peer = teacher('question_peer')
        self.other_grade = teacher('question_other_grade', '八年级')
        self.owner_auth = auth(self.owner)
        self.peer_auth = auth(self.peer)
        self.other_auth = auth(self.other_grade)
        self.root = AIUnit.objects.create(
            grade='七年级', name='root', display_name='AI 基础', created_by=self.owner,
        )
        self.section = AIUnit.objects.create(
            grade='七年级', parent=self.root, name='section', display_name='第一节',
            created_by=self.owner,
        )

    def _create(self, **overrides):
        return self.client.post(
            '/api/ai/admin/choice-questions/',
            question_payload(self.section.pk, **overrides),
            format='json', **self.owner_auth,
        )

    def test_create_filter_detail_and_grade_scope(self):
        created = self._create()
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data['grade'], '七年级')
        self.assertEqual(created.data['big_unit_name'], 'AI 基础')
        self.assertEqual(created.data['management_version'], 1)

        filtered = self.client.get(
            '/api/ai/admin/choice-questions/?difficulty=easy&q=图像', **self.owner_auth,
        )
        self.assertEqual(len(filtered.data), 1)
        detail = self.client.get(
            f"/api/ai/admin/choice-questions/{created.data['id']}/", **self.owner_auth,
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data['answer'], 'A')
        hidden = self.client.get('/api/ai/admin/choice-questions/', **self.other_auth)
        self.assertEqual(hidden.data, [])

    def test_owner_rule_version_conflict_and_permanent_delete(self):
        created = self._create()
        question_id = created.data['id']
        peer_edit = self.client.patch(
            f'/api/ai/admin/choice-questions/{question_id}/',
            {'expected_version': 1, 'text': '同年级其他教师修改'},
            format='json', **self.peer_auth,
        )
        self.assertEqual(peer_edit.status_code, 403)
        self.assertEqual(peer_edit.data['code'], 'content_owner_required')

        updated = self.client.patch(
            f'/api/ai/admin/choice-questions/{question_id}/',
            {'expected_version': 1, 'text': '更新后的题干'},
            format='json', **self.owner_auth,
        )
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(updated.data['management_version'], 2)
        conflict = self.client.patch(
            f'/api/ai/admin/choice-questions/{question_id}/',
            {'expected_version': 1, 'text': '过期修改'},
            format='json', **self.owner_auth,
        )
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.data['management_version'], 2)

        copied = self.client.post(
            f'/api/ai/admin/choice-questions/{question_id}/copy/',
            {}, format='json', **self.peer_auth,
        )
        self.assertEqual(copied.status_code, 201, copied.data)
        self.assertNotEqual(copied.data['id'], question_id)
        self.assertEqual(copied.data['created_by'], self.peer.pk)
        self.assertTrue(copied.data['can_edit_content'])

        deleted = self.client.delete(
            f'/api/ai/admin/choice-questions/{question_id}/',
            {'expected_version': 2}, format='json', **self.owner_auth,
        )
        self.assertEqual(deleted.status_code, 204)
        active_ids = {
            item['id'] for item in self.client.get(
                '/api/ai/admin/choice-questions/', **self.owner_auth,
            ).data
        }
        self.assertNotIn(question_id, active_ids)
        self.assertIn(copied.data['id'], active_ids)
        self.assertFalse(AIChoiceQuestion.objects.filter(pk=question_id).exists())

    def test_bulk_delete_choice_questions_is_all_or_nothing(self):
        first = self._create(text='第一题').data
        second = self._create(text='第二题').data
        stale = self.client.post(
            '/api/ai/admin/choice-questions/bulk-delete/',
            {'items': [
                {'id': first['id'], 'expected_version': 1},
                {'id': second['id'], 'expected_version': 2},
            ]}, format='json', **self.owner_auth,
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(
            AIChoiceQuestion.objects.filter(pk__in=[first['id'], second['id']]).count(),
            2,
        )
        deleted = self.client.post(
            '/api/ai/admin/choice-questions/bulk-delete/',
            {'items': [
                {'id': first['id'], 'expected_version': 1},
                {'id': second['id'], 'expected_version': 1},
            ]}, format='json', **self.owner_auth,
        )
        self.assertEqual(deleted.status_code, 200, deleted.data)
        self.assertEqual(deleted.data['deleted_count'], 2)
        self.assertFalse(
            AIChoiceQuestion.objects.filter(pk__in=[first['id'], second['id']]).exists(),
        )

    def test_rejects_root_unit_blank_option_and_student_access(self):
        invalid_root = self.client.post(
            '/api/ai/admin/choice-questions/', question_payload(self.root.pk),
            format='json', **self.owner_auth,
        )
        self.assertEqual(invalid_root.status_code, 400)
        self.assertEqual(invalid_root.data['code'], 'leaf_unit_required')
        blank = self._create(option_b='   ')
        self.assertEqual(blank.status_code, 400)
        self.assertEqual(blank.data['code'], 'validation_error')

        student = CustomUser.objects.create_user(
            username='question_student', password='test123', role='student',
            grade='七年级', class_num='1', student_number='1',
        )
        denied = self.client.get('/api/ai/admin/choice-questions/', **auth(student))
        self.assertEqual(denied.status_code, 403)

    def test_json_import_is_compatible_and_atomic(self):
        compatible_payload = {
            'grade': '七年级',
            'unit': 'section',
            'unit_display_name': '第一节',
            'questions': [{
                'difficulty': 'medium',
                'category': '机器学习',
                'text': '监督学习需要什么？',
                'options': [
                    {'key': 'A', 'text': '带标签数据'},
                    {'key': 'B', 'text': '只有空文件'},
                    {'key': 'C', 'text': '纸笔'},
                    {'key': 'D', 'text': '不需要数据'},
                ],
                'answer': 'A',
                'explanation': '监督学习使用带标签数据。',
            }],
        }
        imported = self.client.post(
            '/api/ai/admin/choice-questions/import/', compatible_payload,
            format='json', **self.owner_auth,
        )
        self.assertEqual(imported.status_code, 201, imported.data)
        self.assertEqual(imported.data['imported'], 1)

        before = AIChoiceQuestion.objects.count()
        invalid_batch = {
            'unit_id': self.section.pk,
            'questions': [
                question_payload(self.section.pk),
                question_payload(self.section.pk, text=''),
            ],
        }
        rejected = self.client.post(
            '/api/ai/admin/choice-questions/import/', invalid_batch,
            format='json', **self.owner_auth,
        )
        self.assertEqual(rejected.status_code, 400, rejected.data)
        self.assertEqual(rejected.data['code'], 'invalid_import_question')
        self.assertEqual(AIChoiceQuestion.objects.count(), before)
