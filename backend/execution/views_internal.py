from django.conf import settings
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .internal_auth import RunnerAuthError, authenticate_runner_request
from .models import RunnerRequestReceipt
from .queue import QueueError, claim_task, complete_task, heartbeat_task, update_runner_node
from .serializers_internal import (
    CompletionSerializer,
    LeaseSerializer,
    ProtocolSerializer,
    RunnerNodeHeartbeatSerializer,
)


class ReplayError(Exception):
    def __init__(self, message, *, code='request_replay_conflict'):
        super().__init__(message)
        self.message = message
        self.code = code


def _json_safe(value):
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return value


def _execute_once(identity, callback, *, replayable=True):
    with transaction.atomic():
        try:
            with transaction.atomic():
                receipt = RunnerRequestReceipt.objects.create(
                    runner_id=identity.runner_id,
                    request_id=identity.request_id,
                    endpoint=identity.endpoint,
                    request_hash=identity.request_hash,
                )
        except IntegrityError:
            receipt = RunnerRequestReceipt.objects.select_for_update().get(
                runner_id=identity.runner_id,
                request_id=identity.request_id,
            )
            if receipt.endpoint != identity.endpoint or receipt.request_hash != identity.request_hash:
                raise ReplayError('请求 ID 已被不同请求使用')
            if receipt.response_status is None:
                raise ReplayError('同一请求正在处理，请稍后重试', code='request_in_progress')
            if not replayable or receipt.response_body is None:
                raise ReplayError('该请求 ID 已处理，不得再次领取任务', code='request_already_processed')
            return receipt.response_body, receipt.response_status, True

        response_body, response_status = callback()
        safe_body = _json_safe(response_body)
        receipt.response_body = safe_body if replayable else None
        receipt.response_status = response_status
        receipt.save(update_fields=('response_body', 'response_status'))
        return safe_body, response_status, False


class RunnerInternalView(APIView):
    authentication_classes = []
    permission_classes = []
    throttle_classes = []

    serializer_class = None
    replayable = True

    def operation(self, identity, data):
        raise NotImplementedError

    def post(self, request, **kwargs):
        try:
            identity = authenticate_runner_request(request)
        except RunnerAuthError as exc:
            return Response({'error': exc.message, 'code': exc.code}, status=exc.status_code)

        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': '参数错误', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if serializer.validated_data['protocol_version'] != settings.RUNNER_PROTOCOL_VERSION:
            return Response(
                {'error': 'Runner 协议版本不匹配', 'code': 'protocol_mismatch'},
                status=status.HTTP_409_CONFLICT,
            )
        if not settings.CODE_EXECUTION_ENABLED:
            return Response(
                {'error': '代码执行服务已关闭', 'code': 'execution_disabled'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        try:
            body, response_status, replayed = _execute_once(
                identity,
                lambda: self.operation(identity, serializer.validated_data, **kwargs),
                replayable=self.replayable,
            )
        except ReplayError as exc:
            return Response({'error': exc.message, 'code': exc.code}, status=status.HTTP_409_CONFLICT)
        except QueueError as exc:
            return Response({'error': exc.message, 'code': exc.code}, status=exc.status_code)
        if replayed:
            body = {**body, 'replayed': True}
        return Response(body, status=response_status)


class ClaimTaskView(RunnerInternalView):
    serializer_class = ProtocolSerializer
    replayable = False

    def operation(self, identity, data):
        task = claim_task(runner_id=identity.runner_id)
        return {'task': task}, status.HTTP_200_OK


class HeartbeatTaskView(RunnerInternalView):
    serializer_class = LeaseSerializer

    def operation(self, identity, data, task_id):
        task_data = heartbeat_task(
            task_id=task_id,
            runner_id=identity.runner_id,
            lease_token=data['lease_token'],
        )
        return task_data, status.HTTP_200_OK


class CompleteTaskView(RunnerInternalView):
    serializer_class = CompletionSerializer

    def operation(self, identity, data, task_id):
        lease_token = data.pop('lease_token')
        data.pop('protocol_version')
        task, applied = complete_task(
            task_id=task_id,
            runner_id=identity.runner_id,
            lease_token=lease_token,
            result=data,
        )
        return {
            'task_id': str(task.public_id),
            'status': task.status,
            'applied': applied,
        }, status.HTTP_200_OK


class RunnerNodeHeartbeatView(RunnerInternalView):
    serializer_class = RunnerNodeHeartbeatSerializer

    def operation(self, identity, data):
        node = update_runner_node(runner_id=identity.runner_id, data=data)
        return {
            'runner_id': node.runner_id,
            'status': node.status,
            'last_heartbeat_at': node.last_heartbeat_at,
        }, status.HTTP_200_OK
