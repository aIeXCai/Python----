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
    programming = serializers.JSONField(required=False)

    def validate_answers(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('答案必须是题目标识到选项的对象')
        return value

    def validate_programming(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('编程答案必须是题目标识到代码和分数的对象')
        for item_id, result in value.items():
            if not isinstance(item_id, str) or not isinstance(result, dict):
                raise serializers.ValidationError('编程答案格式不正确')
            code = result.get('code')
            score = result.get('score')
            if not isinstance(code, str):
                raise serializers.ValidationError('代码必须是文本')
            if score is not None and (
                isinstance(score, bool) or not isinstance(score, (int, float))
                or not 0 <= score <= 100
            ):
                raise serializers.ValidationError('本地分数必须在 0 到 100 之间')
        return value
