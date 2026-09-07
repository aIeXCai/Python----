from rest_framework import serializers
from .models import Problem, Submission
from users.grade_levels import GRADE_CHOICES, normalize_grade, normalize_student_identifier
from users.scopes import is_platform_admin

from .problem_management import publication_data, publication_label


class ProblemListSerializer(serializers.ModelSerializer):
    """题目列表序列化器（不含题目描述和测试点详情）"""
    test_count = serializers.IntegerField(source='get_test_count', read_only=True)

    class Meta:
        model = Problem
        fields = ['problem_id', 'title', 'difficulty', 'grade_tag', 'test_count', 'created_at']


class TestCaseSerializer(serializers.Serializer):
    """测试点序列化器"""
    number = serializers.IntegerField()
    input = serializers.CharField()
    output = serializers.CharField()


class ProblemDetailSerializer(serializers.ModelSerializer):
    """题目详情序列化器（含测试点）"""
    test_cases = serializers.SerializerMethodField()
    template_code = serializers.SerializerMethodField()

    class Meta:
        model = Problem
        fields = ['problem_id', 'title', 'description', 'difficulty', 'grade_tag', 'template_code', 'test_cases', 'created_at']

    def get_test_cases(self, obj):
        return obj.get_test_cases()

    def get_template_code(self, obj):
        return obj.get_template_code()


class SubmissionCreateSerializer(serializers.Serializer):
    """提交代码序列化器"""
    problem_id = serializers.CharField()
    code = serializers.CharField()

    def validate_code(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("代码不能为空")
        return value


class SubmissionResultSerializer(serializers.Serializer):
    """提交结果序列化器"""
    score = serializers.FloatField()
    status = serializers.CharField()
    error_message = serializers.CharField(required=False, allow_blank=True)
    detail = serializers.CharField(required=False, allow_blank=True)


class SubmissionHistorySerializer(serializers.ModelSerializer):
    """提交历史序列化器"""
    problem_id = serializers.CharField(source='problem.problem_id')

    class Meta:
        model = Submission
        fields = [
            'id', 'problem_id', 'score', 'status', 'error_message',
            'submitted_at',
        ]


class ScoreSerializer(serializers.Serializer):
    """单个成绩项序列化器"""
    problem_id = serializers.CharField()
    best_score = serializers.FloatField()
    attempts = serializers.IntegerField()
    status = serializers.CharField()


class StudentStatsSerializer(serializers.Serializer):
    """学生学习统计序列化器"""
    total_problems = serializers.IntegerField()
    completed_problems = serializers.IntegerField()
    average_score = serializers.FloatField()
    rank = serializers.IntegerField()


class AdminStatsSerializer(serializers.Serializer):
    """管理后台统计序列化器"""
    total_students = serializers.IntegerField()
    total_problems = serializers.IntegerField()
    today_submissions = serializers.IntegerField()
    avg_score = serializers.FloatField()


class AdminProblemListSerializer(serializers.ModelSerializer):
    test_count = serializers.IntegerField(source='get_test_count', read_only=True)
    publication_label = serializers.SerializerMethodField()
    publication = serializers.SerializerMethodField()
    can_edit_content = serializers.SerializerMethodField()
    can_archive = serializers.SerializerMethodField()

    class Meta:
        model = Problem
        fields = [
            'problem_id', 'title', 'description', 'difficulty', 'grade_tag', 'course',
            'template_code', 'test_count', 'created_by', 'publishing_suspended',
            'management_version', 'archived_at', 'created_at', 'updated_at',
            'publication_label', 'publication', 'can_edit_content', 'can_archive',
        ]

    def _actor(self):
        request = self.context.get('request')
        return getattr(request, 'user', None)

    def get_publication_label(self, obj):
        try:
            return publication_label(obj, self._actor())
        except Exception:
            return '不可见'

    def get_publication(self, obj):
        try:
            return publication_data(obj, self._actor())
        except Exception:
            return {
                'problem_id': obj.problem_id,
                'management_version': obj.management_version,
                'publishing_suspended': obj.publishing_suspended,
                'all_school': False,
                'scopes': [],
            }

    def get_can_edit_content(self, obj):
        actor = self._actor()
        return bool(is_platform_admin(actor) or obj.created_by_id == getattr(actor, 'pk', None))

    def get_can_archive(self, obj):
        return is_platform_admin(self._actor())


class AdminProblemDetailSerializer(AdminProblemListSerializer):
    pass


class ProblemContentUpdateSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)
    difficulty = serializers.CharField(max_length=20, required=False, allow_blank=True)
    grade_tag = serializers.ChoiceField(
        choices=GRADE_CHOICES, required=False, allow_blank=True,
    )
    template_code = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)

    def validate(self, attrs):
        if not any(field in attrs for field in ('title', 'description', 'difficulty', 'grade_tag', 'template_code')):
            raise serializers.ValidationError('至少需要提交一个可编辑字段')
        return attrs


class TeacherProblemAudienceUpdateSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    visible = serializers.BooleanField()
    all_classes = serializers.BooleanField(default=False)
    classes = serializers.ListField(
        child=serializers.CharField(max_length=20, trim_whitespace=True),
        default=list,
    )

    def validate(self, attrs):
        classes = []
        for value in attrs.get('classes', []):
            normalized = normalize_student_identifier(value, label='班级')
            if normalized not in classes:
                classes.append(normalized)
        attrs['classes'] = classes
        if attrs['visible'] and not attrs['all_classes'] and not classes:
            raise serializers.ValidationError({'classes': '指定范围至少需要选择一个班级'})
        return attrs


class AdminGradeScopeSerializer(serializers.Serializer):
    grade = serializers.ChoiceField(choices=GRADE_CHOICES)
    visible = serializers.BooleanField(default=True)
    all_classes = serializers.BooleanField(default=False)
    classes = serializers.ListField(
        child=serializers.CharField(max_length=20, trim_whitespace=True),
        default=list,
    )

    def validate(self, attrs):
        attrs['grade'] = normalize_grade(attrs['grade'])
        classes = []
        for value in attrs.get('classes', []):
            normalized = normalize_student_identifier(value, label='班级')
            if normalized not in classes:
                classes.append(normalized)
        attrs['classes'] = classes
        if attrs['visible'] and not attrs['all_classes'] and not classes:
            raise serializers.ValidationError({'classes': '指定范围至少需要选择一个班级'})
        return attrs


class AdminProblemAudienceUpdateSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    publishing_suspended = serializers.BooleanField()
    all_school = serializers.BooleanField()
    scopes = AdminGradeScopeSerializer(many=True)

    def validate_scopes(self, value):
        grades = [scope['grade'] for scope in value]
        if len(grades) != len(set(grades)):
            raise serializers.ValidationError('同一年级不能重复配置')
        return value


class ProblemVersionSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
