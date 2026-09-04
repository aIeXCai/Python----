from rest_framework import serializers

from .constants import GRADE_RESULT_STATUSES, RUNNER_STATUS_DRAINING, RUNNER_STATUS_ONLINE


class ProtocolSerializer(serializers.Serializer):
    protocol_version = serializers.CharField(max_length=32)


class LeaseSerializer(ProtocolSerializer):
    lease_token = serializers.CharField(min_length=32, max_length=200, trim_whitespace=False)


class CompletionSerializer(LeaseSerializer):
    status = serializers.ChoiceField(choices=GRADE_RESULT_STATUSES)
    stdout = serializers.CharField(required=False, allow_blank=True, default='', trim_whitespace=False)
    stderr = serializers.CharField(required=False, allow_blank=True, default='', trim_whitespace=False)
    execution_ms = serializers.IntegerField(min_value=0)
    score = serializers.FloatField(required=False, allow_null=True, min_value=0, max_value=100)
    detail = serializers.JSONField(required=False, default=dict)


class RunnerNodeHeartbeatSerializer(ProtocolSerializer):
    sandbox_image_digest = serializers.CharField(min_length=16, max_length=200)
    capacity = serializers.IntegerField(min_value=1, max_value=100)
    active_slots = serializers.IntegerField(min_value=0, max_value=100)
    status = serializers.ChoiceField(choices=(RUNNER_STATUS_ONLINE, RUNNER_STATUS_DRAINING))
    last_error = serializers.CharField(required=False, allow_blank=True, max_length=500, default='')

    def validate(self, attrs):
        if attrs['active_slots'] > attrs['capacity']:
            raise serializers.ValidationError({'active_slots': '不能大于 capacity'})
        return attrs
