from rest_framework import serializers

from .constants import TASK_TYPE_CHOICES, TASK_TYPE_GRADE


class CodeRunCreateSerializer(serializers.Serializer):
    code = serializers.CharField(trim_whitespace=False)
    stdin = serializers.CharField(required=False, allow_blank=True, default='', trim_whitespace=False)

    def validate_code(self, value):
        if not value.strip():
            raise serializers.ValidationError('代码不能为空')
        return value


class ActiveTaskQuerySerializer(serializers.Serializer):
    problem_id = serializers.CharField(required=False)
    task_type = serializers.ChoiceField(choices=TASK_TYPE_CHOICES)

    def validate(self, attrs):
        if attrs['task_type'] == TASK_TYPE_GRADE and not attrs.get('problem_id'):
            raise serializers.ValidationError({'problem_id': '查询评测任务时必填'})
        return attrs


def public_task_data(task):
    data = {
        'task_id': str(task.public_id),
        'task_type': task.task_type,
        'status': task.status,
        'queued_at': task.queued_at,
        'started_at': task.started_at,
        'finished_at': task.finished_at,
        'poll_after_ms': 500 if task.status == 'queued' else 1000,
    }
    submission = getattr(task, 'submission', None)
    if submission:
        data['submission_id'] = submission.id
    if task.status not in ('queued', 'running'):
        data.update({
            'output': task.stdout,
            'error': task.stderr,
            'detail': task.result_detail,
            'execution_ms': task.execution_ms,
        })
        if task.task_type == TASK_TYPE_GRADE:
            data['score'] = task.score
    return data
