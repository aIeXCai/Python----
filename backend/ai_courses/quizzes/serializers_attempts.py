"""Strict student request contracts for AI quiz attempts."""

from rest_framework import serializers


class AIQuizAttemptAnswersSerializer(serializers.Serializer):
    attempt_id = serializers.IntegerField(min_value=1)
    revision = serializers.IntegerField(min_value=0)
    answers = serializers.JSONField()

    def validate_answers(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('答案必须是题目标识到选项的对象')
        return value


class AIQuizAttemptSubmitSerializer(serializers.Serializer):
    attempt_id = serializers.IntegerField(min_value=1)
    revision = serializers.IntegerField(min_value=0)
    answers = serializers.JSONField()

    def validate_answers(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('答案必须是题目标识到选项的对象')
        return value
