from rest_framework import serializers
from .models import Problem, Submission


class ProblemListSerializer(serializers.ModelSerializer):
    """题目列表序列化器（不含题目描述和测试点详情）"""
    test_count = serializers.IntegerField(source='get_test_count', read_only=True)

    class Meta:
        model = Problem
        fields = ['problem_id', 'title', 'difficulty', 'test_count', 'created_at']


class TestCaseSerializer(serializers.Serializer):
    """测试点序列化器"""
    number = serializers.IntegerField()
    input = serializers.CharField()
    output = serializers.CharField()


class ProblemDetailSerializer(serializers.ModelSerializer):
    """题目详情序列化器（含测试点）"""
    test_cases = serializers.SerializerMethodField()

    class Meta:
        model = Problem
        fields = ['problem_id', 'title', 'description', 'difficulty', 'test_cases', 'created_at']

    def get_test_cases(self, obj):
        return obj.get_test_cases()


class SubmissionCreateSerializer(serializers.Serializer):
    """提交代码序列化器"""
    problem_id = serializers.CharField()
    code = serializers.CharField()

    def validate_code(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("代码不能为空")
        return value.strip()


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
        fields = ['id', 'problem_id', 'score', 'status', 'submitted_at']


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
