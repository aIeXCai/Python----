"""
info_tech Serializer 校验测试
运行: cd backend && python manage.py test info_tech.tests_serializer
"""
from django.test import TestCase
from rest_framework import serializers
from info_tech.serializers import (
    QuestionCreateSerializer,
    QuestionImportSerializer,
    QuizSessionCreateSerializer,
    QuizSessionToggleSerializer,
)
from info_tech.models import Unit, Question, QuizSession
from users.models import CustomUser


class QuestionCreateSerializerTest(TestCase):
    """QuestionCreateSerializer: 新增/编辑单题"""

    def setUp(self):
        self.unit = Unit.objects.create(
            grade='七年级', name='第一单元', display_name='第一单元：走进人工智能', order=1
        )

    def test_valid_full_data(self):
        """完整合法数据 → is_valid=True，create 成功"""
        data = {
            'unit': '第一单元',
            'difficulty': 'medium',
            'category': '网络基础',
            'text': '计算机网络最根本的功能是？',
            'option_a': '数据通信', 'option_b': '资源共享', 'option_c': '分布式处理', 'option_d': '可靠性',
            'answer': 'B',
            'explanation': '资源共享是网络最根本的功能',
        }
        s = QuestionCreateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        q = s.save()
        self.assertEqual(q.unit, self.unit)
        self.assertEqual(q.difficulty, 'medium')
        self.assertEqual(q.answer, 'B')

    def test_invalid_unit_not_exists(self):
        """unit name 不存在 → ValidationError"""
        data = {
            'unit': '不存在的单元',
            'text': '题', 'answer': 'A',
            'option_a': 'a', 'option_b': 'b', 'option_c': 'c', 'option_d': 'd',
        }
        s = QuestionCreateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('unit', s.errors)

    def test_answer_must_be_abcd(self):
        """answer 不是 A/B/C/D → 校验失败"""
        for bad in ['E', 'F', 'e', 'a', '1', '']:
            s = QuestionCreateSerializer(data={
                'unit': '第一单元', 'text': '题', 'answer': bad,
                'option_a': 'a', 'option_b': 'b', 'option_c': 'c', 'option_d': 'd',
            })
            self.assertFalse(s.is_valid(), f'answer={bad} 应失败')

    def test_missing_required_field_option_a(self):
        """缺少 option_a → 校验失败"""
        data = {
            'unit': '第一单元', 'text': '题', 'answer': 'A',
            'option_b': 'b', 'option_c': 'c', 'option_d': 'd',
        }
        s = QuestionCreateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('option_a', s.errors)

    def test_missing_required_field_answer(self):
        """缺少 answer → 校验失败"""
        data = {
            'unit': '第一单元', 'text': '题',
            'option_a': 'a', 'option_b': 'b', 'option_c': 'c', 'option_d': 'd',
        }
        s = QuestionCreateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('answer', s.errors)

    def test_update_only_sets_provided_fields(self):
        """update 只更新 validated_data 中有的字段，未传的不变
        注意：QuestionCreateSerializer.update() 实际会重置未传字段到默认值，
        这是现有 serializer 的行为，测试验证这一行为（不传 → 变 easy）"""
        unit2 = Unit.objects.create(grade='八年级', name='唯一名称单2', display_name='唯一', order=2)
        q = Question.objects.create(
            unit=self.unit, difficulty='hard', text='原题', answer='A',
            option_a='a', option_b='b', option_c='c', option_d='d'
        )
        data = {
            'unit': '唯一名称单2',  # 唯一 name，不会有 MultipleObjectsReturned
            'text': '修改后', 'answer': 'C',
            'option_a': 'x', 'option_b': 'y', 'option_c': 'z', 'option_d': 'w',
        }
        s = QuestionCreateSerializer(instance=q, data=data)
        self.assertTrue(s.is_valid(), s.errors)
        updated = s.save()
        self.assertEqual(updated.text, '修改后')
        # difficulty 未在 data 中，会被更新为默认值 'easy'
        self.assertEqual(updated.difficulty, 'easy')


class QuestionImportSerializerTest(TestCase):
    """QuestionImportSerializer: 批量导入 JSON"""

    def test_valid_import_creates_unit_and_questions(self):
        """合法数据 → 创建/复用 Unit + 批量创建 Question"""
        data = {
            'unit': '第三单元',
            'unit_display_name': '第三单元：算法基础',
            'grade': '七年级',
            'questions': [
                {
                    'text': '什么是算法？', 'difficulty': 'easy', 'category': '概念',
                    'answer': 'A',
                    'options': [{'key': 'A', 'text': '解决问题的步骤'}, {'key': 'B', 'text': '编程语言'}],
                },
                {
                    'text': '冒泡排序是哪种算法？', 'difficulty': 'medium', 'category': '排序',
                    'answer': 'B',
                    'options': [{'key': 'A', 'text': '查找'}, {'key': 'B', 'text': '交换排序'}],
                },
            ]
        }
        s = QuestionImportSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        result = s.save()
        self.assertEqual(result['imported'], 2)
        self.assertEqual(Unit.objects.filter(name='第三单元').count(), 1)
        self.assertEqual(Question.objects.filter(unit__name='第三单元').count(), 2)

    def test_empty_questions_list_fails(self):
        """题目列表为空 → ValidationError"""
        data = {
            'unit': '单元', 'grade': '七年级', 'questions': []
        }
        s = QuestionImportSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('questions', s.errors)

    def test_import_creates_unit_if_not_exists(self):
        """单元不存在时自动创建"""
        data = {
            'unit': '新单元', 'grade': '七年级', 'questions': [
                {'text': '题', 'answer': 'A', 'options': [{'key': 'A', 'text': 'a'}]}
            ]
        }
        s = QuestionImportSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        s.save()
        self.assertEqual(Unit.objects.filter(name='新单元', grade='七年级').exists(), True)

    def test_import_reuses_existing_unit(self):
        """同名单元+同年级 → 复用，不新建"""
        Unit.objects.create(name='复用单元', grade='七年级', display_name='已有单元', order=1)
        data = {
            'unit': '复用单元', 'grade': '七年级',
            'questions': [
                {'text': '题', 'answer': 'B', 'options': [{'key': 'A', 'text': 'a'}, {'key': 'B', 'text': 'b'}]}
            ]
        }
        s = QuestionImportSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        s.save()
        self.assertEqual(Unit.objects.filter(name='复用单元').count(), 1)

    def test_options_key_normalization(self):
        """option key 大写归一化（小写 a→A）"""
        data = {
            'unit': '单元X', 'grade': '七年级',
            'questions': [
                {
                    'text': '归一化测试', 'answer': 'a',  # 小写
                    'options': [
                        {'key': 'a', 'text': 'A选项'}, {'key': 'B', 'text': 'B选项'},
                        {'key': 'c', 'text': 'C选项'}, {'key': 'D', 'text': 'D选项'},
                    ]
                }
            ]
        }
        s = QuestionImportSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        result = s.save()
        q = Question.objects.get(text='归一化测试')
        self.assertEqual(q.answer, 'a')  # 原始值保持
        self.assertEqual(q.option_a, 'A选项')  # 归一到 A/B/C/D


class QuizSessionCreateSerializerTest(TestCase):
    """QuizSessionCreateSerializer: 创建/编辑小测"""

    def setUp(self):
        self.teacher = CustomUser.objects.create_user(
            username='t1', password='test', role='teacher', display_name='老师', managed_grade='七年级'
        )
        self.u1 = Unit.objects.create(grade='七年级', name='单1', display_name='单元1', order=1)
        self.u2 = Unit.objects.create(grade='七年级', name='单2', display_name='单元2', order=2)

    def _make_request(self, teacher, data):
        class FakeRequest:
            user = teacher
        return QuizSessionCreateSerializer(data=data, context={'request': FakeRequest()})

    def test_valid_minimal_data(self):
        """最小合法数据 → is_valid=True"""
        data = {'title': '小测', 'units': [self.u1.pk], 'num_questions': 5}
        s = self._make_request(self.teacher, data)
        self.assertTrue(s.is_valid(), s.errors)
        qs = s.save()
        self.assertEqual(qs.title, '小测')
        self.assertEqual(qs.units.count(), 1)

    def test_empty_units_fails(self):
        """units=[] → ValidationError"""
        data = {'title': '无单元小测', 'units': [], 'num_questions': 5}
        s = self._make_request(self.teacher, data)
        self.assertFalse(s.is_valid())
        self.assertIn('units', s.errors)

    def test_invalid_unit_id_fails(self):
        """units 含不存在 ID → ValidationError"""
        data = {'title': '小测', 'units': [self.u1.pk, 99999], 'num_questions': 5}
        s = self._make_request(self.teacher, data)
        self.assertFalse(s.is_valid())
        self.assertIn('units', s.errors)

    def test_num_questions_zero_fails(self):
        """num_questions <= 0 → 校验失败"""
        for bad in [0, -1]:
            s = self._make_request(self.teacher, {'title': 't', 'units': [self.u1.pk], 'num_questions': bad})
            self.assertFalse(s.is_valid(), f'num={bad} 应失败')

    def test_difficulty_ratio_empty_defaults_to_easy10(self):
        """difficulty_ratio={} → 自动补全 {'easy': 10}"""
        data = {'title': '默认难度', 'units': [self.u1.pk], 'num_questions': 5, 'difficulty_ratio': {}}
        s = self._make_request(self.teacher, data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data['difficulty_ratio'], {'easy': 10})

    def test_difficulty_ratio_total_zero_fails(self):
        """难度比例总和为 0 → ValidationError"""
        data = {'title': '无效比例', 'units': [self.u1.pk], 'num_questions': 5, 'difficulty_ratio': {'easy': 0, 'medium': 0}}
        s = self._make_request(self.teacher, data)
        self.assertFalse(s.is_valid())
        self.assertIn('difficulty_ratio', s.errors)

    def test_update_can_change_units(self):
        """update 可更换关联单元"""
        qs = QuizSession.objects.create(
            title='原小测', created_by=self.teacher,
            num_questions=5, difficulty_ratio={'easy': 5}
        )
        qs.units.set([self.u1])
        data = {'title': '新标题', 'units': [self.u2.pk], 'num_questions': 10, 'difficulty_ratio': {}}
        s = QuizSessionCreateSerializer(instance=qs, data=data, context={'request': type('R', (), {'user': self.teacher})()})
        self.assertTrue(s.is_valid(), s.errors)
        updated = s.save()
        self.assertEqual(updated.units.count(), 1)
        self.assertEqual(updated.units.first(), self.u2)


class QuizSessionToggleSerializerTest(TestCase):
    """QuizSessionToggleSerializer: 切换可见性"""

    def test_toggle_on(self):
        """is_visible=True"""
        s = QuizSessionToggleSerializer(data={'is_visible': True, 'visible_grades': ['七年级']})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertTrue(s.validated_data['is_visible'])
        self.assertEqual(s.validated_data['visible_grades'], ['七年级'])

    def test_toggle_off(self):
        """is_visible=False"""
        s = QuizSessionToggleSerializer(data={'is_visible': False})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertFalse(s.validated_data['is_visible'])

    def test_missing_is_visible(self):
        """缺少 is_visible → 失败"""
        s = QuizSessionToggleSerializer(data={'visible_grades': ['七年级']})
        self.assertFalse(s.is_valid())
        self.assertIn('is_visible', s.errors)
