"""Teacher-facing contracts for AI quiz configuration and publishing."""

from decimal import Decimal

from rest_framework import serializers

from users.grade_levels import GRADE_CHOICES

from .models import AIChoiceQuestion, AIQuizSession


class AIQuizProgrammingItemInputSerializer(serializers.Serializer):
    problem_id = serializers.CharField(max_length=50)
    position = serializers.IntegerField(min_value=1, max_value=32767)
    points = serializers.DecimalField(max_digits=5, decimal_places=1, min_value=Decimal('0.1'))


class AIQuizAudienceRuleInputSerializer(serializers.Serializer):
    scope_type = serializers.ChoiceField(choices=('all_school', 'grade_all', 'class'))
    grade = serializers.ChoiceField(choices=GRADE_CHOICES, required=False, allow_blank=True)
    class_num = serializers.CharField(max_length=20, required=False, allow_blank=True)
    is_active = serializers.BooleanField(default=True)


class AIQuizWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, trim_whitespace=False)
    content_grade = serializers.ChoiceField(choices=GRADE_CHOICES)
    choice_unit_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, default=list,
    )
    choice_question_count = serializers.IntegerField(min_value=0, max_value=32767, default=0)
    choice_difficulty_ratio = serializers.DictField(required=False, default=dict)
    choice_points = serializers.DecimalField(
        max_digits=5, decimal_places=1, min_value=Decimal('0'),
        max_value=Decimal('100.0'), default=Decimal('0'),
    )
    programming_items = AIQuizProgrammingItemInputSerializer(many=True, required=False, default=list)
    audience = AIQuizAudienceRuleInputSerializer(many=True, required=False)
    time_limit = serializers.IntegerField(
        min_value=1, max_value=600, allow_null=True, required=False, default=None,
    )

    def validate_choice_unit_ids(self, values):
        if len(values) != len(set(values)):
            raise serializers.ValidationError('选择题小节不能重复')
        return values

    def validate_choice_difficulty_ratio(self, value):
        allowed = {key for key, _label in AIChoiceQuestion.DIFFICULTY_CHOICES}
        unknown = set(value) - allowed
        if unknown:
            raise serializers.ValidationError('难度题数仅支持 easy、medium、hard')
        normalized = {}
        for key in allowed:
            raw = value.get(key, 0)
            if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
                raise serializers.ValidationError(f'{key} 题数必须是非负整数')
            normalized[key] = raw
        return normalized


class AIQuizUpdateSerializer(AIQuizWriteSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    title = serializers.CharField(max_length=200, trim_whitespace=False, required=False)
    content_grade = serializers.ChoiceField(choices=GRADE_CHOICES, required=False)
    choice_unit_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False,
    )
    choice_question_count = serializers.IntegerField(
        min_value=0, max_value=32767, required=False,
    )
    choice_difficulty_ratio = serializers.DictField(required=False)
    choice_points = serializers.DecimalField(
        max_digits=5, decimal_places=1, min_value=Decimal('0'),
        max_value=Decimal('100.0'), required=False,
    )
    programming_items = AIQuizProgrammingItemInputSerializer(many=True, required=False)
    time_limit = serializers.IntegerField(
        min_value=1, max_value=600, allow_null=True, required=False,
    )

    def validate(self, attrs):
        if not any(key != 'expected_version' for key in attrs):
            raise serializers.ValidationError('至少需要提交一个可编辑字段')
        return attrs


class AIQuizVersionSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)


class AIQuizCopySerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False, trim_whitespace=False)


class AIQuizAttemptResetSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=300, trim_whitespace=True)


class AIQuizAudienceUpdateSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    audience = AIQuizAudienceRuleInputSerializer(many=True, allow_empty=True)


class AIQuizProgrammingItemSerializer(serializers.Serializer):
    problem_id = serializers.CharField(source='problem.problem_id')
    title = serializers.CharField(source='problem.title')
    unit_id = serializers.IntegerField(source='problem.unit_id', allow_null=True)
    position = serializers.IntegerField()
    points = serializers.DecimalField(max_digits=5, decimal_places=1)


class AIQuizAudienceRuleSerializer(serializers.Serializer):
    scope_type = serializers.CharField()
    grade = serializers.CharField()
    class_num = serializers.CharField()
    is_active = serializers.BooleanField()


class AIQuizSessionSerializer(serializers.ModelSerializer):
    choice_unit_ids = serializers.SerializerMethodField()
    programming_items = AIQuizProgrammingItemSerializer(many=True, read_only=True)
    audience = serializers.SerializerMethodField()
    programming_points = serializers.SerializerMethodField()
    total_points = serializers.SerializerMethodField()
    total_question_count = serializers.SerializerMethodField()
    content_locked = serializers.SerializerMethodField()

    class Meta:
        model = AIQuizSession
        fields = [
            'id', 'title', 'content_grade', 'created_by', 'choice_unit_ids',
            'choice_question_count', 'choice_difficulty_ratio', 'choice_points',
            'programming_items', 'programming_points', 'total_points',
            'total_question_count', 'time_limit', 'status', 'management_version',
            'blueprint_version', 'blueprint_hash', 'content_locked', 'audience',
            'opened_at', 'closed_at', 'archived_at', 'created_at', 'updated_at',
        ]

    def get_choice_unit_ids(self, obj):
        return [unit.pk for unit in obj.choice_units.all()]

    def get_audience(self, obj):
        rules = obj.audience_rules.all().order_by('scope_type', 'grade', 'class_num')
        return AIQuizAudienceRuleSerializer(rules, many=True).data

    def get_programming_points(self, obj):
        return format(sum((item.points for item in obj.programming_items.all()), Decimal('0')), '.1f')

    def get_total_points(self, obj):
        programming = sum((item.points for item in obj.programming_items.all()), Decimal('0'))
        return format(obj.choice_points + programming, '.1f')

    def get_total_question_count(self, obj):
        return obj.choice_question_count + len(list(obj.programming_items.all()))

    def get_content_locked(self, obj):
        return obj.blueprint_version > 0
