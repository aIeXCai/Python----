"""Request and response contracts for the AI question-bank management API."""

from rest_framework import serializers

from users.grade_levels import GRADE_CHOICES
from users.scopes import is_platform_admin

from .models import AIChoiceQuestion, AIUnit


class AIUnitSectionSerializer(serializers.ModelSerializer):
    choice_question_count = serializers.SerializerMethodField()
    programming_problem_count = serializers.SerializerMethodField()
    effectively_archived = serializers.BooleanField(source='is_effectively_archived', read_only=True)
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = AIUnit
        fields = [
            'id', 'grade', 'parent', 'name', 'display_name', 'order',
            'choice_question_count', 'programming_problem_count',
            'archived_at', 'effectively_archived', 'can_delete', 'created_by',
            'created_at', 'updated_at',
        ]

    def get_choice_question_count(self, obj):
        if hasattr(obj, 'active_choice_question_count'):
            return obj.active_choice_question_count
        return obj.choice_questions.filter(archived_at__isnull=True).count()

    def get_programming_problem_count(self, obj):
        if hasattr(obj, 'active_programming_problem_count'):
            return obj.active_programming_problem_count
        return obj.programming_problems.filter(archived_at__isnull=True).count()

    def get_can_delete(self, obj):
        return not (
            # Query all children explicitly: the list view may have prefetched
            # only active sections, but archived children still block deletion.
            AIUnit.objects.filter(parent_id=obj.pk).exists()
            or obj.choice_questions.exists()
            or obj.programming_problems.exists()
            or obj.quiz_sessions.exists()
        )


class AIUnitSerializer(AIUnitSectionSerializer):
    sections = serializers.SerializerMethodField()

    class Meta(AIUnitSectionSerializer.Meta):
        fields = [*AIUnitSectionSerializer.Meta.fields, 'sections']

    def get_sections(self, obj):
        include_archived = self.context.get('include_archived', False)
        sections = list(obj.sections.all())
        if not include_archived:
            sections = [section for section in sections if section.archived_at is None]
        sections.sort(key=lambda section: (section.order, section.pk))
        return AIUnitSectionSerializer(
            sections, many=True, context=self.context,
        ).data


class AIUnitWriteSerializer(serializers.Serializer):
    grade = serializers.ChoiceField(choices=GRADE_CHOICES, required=False)
    parent = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    name = serializers.CharField(max_length=100, required=False)
    display_name = serializers.CharField(max_length=200, required=False)
    order = serializers.IntegerField(required=False, default=0)

    def validate(self, attrs):
        if not self.partial and not attrs.get('name'):
            raise serializers.ValidationError({'name': '单元名称不能为空'})
        if self.partial and not attrs:
            raise serializers.ValidationError('至少需要提交一个可编辑字段')
        return attrs


class AIChoiceQuestionSerializer(serializers.ModelSerializer):
    grade = serializers.CharField(source='unit.grade', read_only=True)
    unit_name = serializers.CharField(source='unit.display_name', read_only=True)
    big_unit_id = serializers.IntegerField(source='unit.parent_id', read_only=True)
    big_unit_name = serializers.CharField(source='unit.parent.display_name', read_only=True)
    effectively_archived = serializers.SerializerMethodField()
    can_edit_content = serializers.SerializerMethodField()

    class Meta:
        model = AIChoiceQuestion
        fields = [
            'id', 'unit', 'grade', 'unit_name', 'big_unit_id', 'big_unit_name',
            'difficulty', 'category', 'text', 'option_a', 'option_b',
            'option_c', 'option_d', 'answer', 'explanation', 'created_by',
            'management_version', 'archived_at', 'effectively_archived',
            'can_edit_content', 'created_at', 'updated_at',
        ]

    def get_effectively_archived(self, obj):
        return bool(obj.archived_at or obj.unit.is_effectively_archived)

    def get_can_edit_content(self, obj):
        request = self.context.get('request')
        actor = getattr(request, 'user', None)
        return bool(is_platform_admin(actor) or obj.created_by_id == getattr(actor, 'pk', None))


class AIChoiceQuestionCreateSerializer(serializers.Serializer):
    unit = serializers.IntegerField(min_value=1)
    difficulty = serializers.ChoiceField(choices=AIChoiceQuestion.DIFFICULTY_CHOICES, default='easy')
    category = serializers.CharField(max_length=100, required=False, default='', allow_blank=True)
    text = serializers.CharField(trim_whitespace=False)
    option_a = serializers.CharField(max_length=500, trim_whitespace=False)
    option_b = serializers.CharField(max_length=500, trim_whitespace=False)
    option_c = serializers.CharField(max_length=500, trim_whitespace=False)
    option_d = serializers.CharField(max_length=500, trim_whitespace=False)
    answer = serializers.ChoiceField(choices=AIChoiceQuestion.ANSWER_CHOICES)
    explanation = serializers.CharField(required=False, default='', allow_blank=True, trim_whitespace=False)


class AIChoiceQuestionUpdateSerializer(AIChoiceQuestionCreateSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    unit = serializers.IntegerField(min_value=1, required=False)
    difficulty = serializers.ChoiceField(
        choices=AIChoiceQuestion.DIFFICULTY_CHOICES, required=False,
    )
    category = serializers.CharField(max_length=100, required=False, allow_blank=True)
    text = serializers.CharField(required=False, trim_whitespace=False)
    option_a = serializers.CharField(max_length=500, required=False, trim_whitespace=False)
    option_b = serializers.CharField(max_length=500, required=False, trim_whitespace=False)
    option_c = serializers.CharField(max_length=500, required=False, trim_whitespace=False)
    option_d = serializers.CharField(max_length=500, required=False, trim_whitespace=False)
    answer = serializers.ChoiceField(choices=AIChoiceQuestion.ANSWER_CHOICES, required=False)
    explanation = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)

    def validate(self, attrs):
        if not any(key != 'expected_version' for key in attrs):
            raise serializers.ValidationError('至少需要提交一个可编辑字段')
        return attrs


class ManagementVersionSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)


class AIChoiceQuestionBulkDeleteItemSerializer(serializers.Serializer):
    id = serializers.IntegerField(min_value=1)
    expected_version = serializers.IntegerField(min_value=1)


class AIChoiceQuestionBulkDeleteSerializer(serializers.Serializer):
    items = AIChoiceQuestionBulkDeleteItemSerializer(many=True, allow_empty=False)

    def validate_items(self, items):
        ids = [item['id'] for item in items]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError('选择题不能重复')
        return items


class AIChoiceQuestionCopySerializer(serializers.Serializer):
    unit = serializers.IntegerField(required=False, min_value=1)


class AIChoiceQuestionImportSerializer(serializers.Serializer):
    unit_id = serializers.IntegerField(required=False, min_value=1)
    unit = serializers.CharField(required=False, max_length=100)
    unit_display_name = serializers.CharField(required=False, allow_blank=True)
    grade = serializers.ChoiceField(choices=GRADE_CHOICES, required=False)
    questions = serializers.ListField(child=serializers.DictField(), allow_empty=False)

    def validate(self, attrs):
        if not attrs.get('unit_id') and not attrs.get('unit'):
            raise serializers.ValidationError({
                'unit_id': '请提交 unit_id，或使用兼容格式提交 grade + unit',
            })
        if attrs.get('unit') and not attrs.get('grade'):
            raise serializers.ValidationError({'grade': '按小节名称导入时必须指定年级'})
        return attrs
