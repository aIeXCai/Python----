"""Strict request contracts for code execution inside an AI quiz attempt."""

from rest_framework import serializers

from execution.constants import TASK_TYPE_CHOICES


class AIQuizRunSerializer(serializers.Serializer):
    attempt_id = serializers.IntegerField(min_value=1)
    code = serializers.CharField(trim_whitespace=False)
    stdin = serializers.CharField(required=False, allow_blank=True, default='', trim_whitespace=False)

    def validate_code(self, value):
        if not value.strip():
            raise serializers.ValidationError('代码不能为空')
        return value


class AIQuizSubmitSerializer(serializers.Serializer):
    attempt_id = serializers.IntegerField(min_value=1)
    code = serializers.CharField(trim_whitespace=False)

    def validate_code(self, value):
        if not value.strip():
            raise serializers.ValidationError('代码不能为空')
        return value


class AIQuizActiveExecutionSerializer(serializers.Serializer):
    attempt_id = serializers.IntegerField(min_value=1)
    task_type = serializers.ChoiceField(choices=TASK_TYPE_CHOICES)
