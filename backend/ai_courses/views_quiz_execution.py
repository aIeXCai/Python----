"""Student programming APIs scoped to the current AI quiz attempt and item."""

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from execution.serializers import public_task_data
from execution.services import ExecutionRequestError
from users.permissions import IsStudent

from .quiz_execution_services import (
    active_attempt_execution,
    enqueue_attempt_grade,
    enqueue_attempt_run,
    programming_item_payload,
)
from .quiz_services import AIQuizServiceError
from .serializers_quiz_execution import (
    AIQuizActiveExecutionSerializer,
    AIQuizRunSerializer,
    AIQuizSubmitSerializer,
)
from .views_quiz_attempts import _error


def _invalid(serializer):
    return Response(
        {'error': '参数错误', 'code': 'invalid_request', 'details': serializer.errors},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _execution_unavailable():
    if not getattr(settings, 'CODE_EXECUTION_ENABLED', False):
        return Response(
            {'error': '代码执行服务暂不可用，请稍后重试'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return None


class AIQuizProgrammingItemView(APIView):
    permission_classes = [IsStudent]

    def get(self, request, pk, item_id):
        try:
            return Response(programming_item_payload(request.user, pk, item_id))
        except AIQuizServiceError as exc:
            return _error(exc)


class AIQuizProgrammingRunView(APIView):
    permission_classes = [IsStudent]

    def post(self, request, pk, item_id):
        unavailable = _execution_unavailable()
        if unavailable:
            return unavailable
        serializer = AIQuizRunSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        values = serializer.validated_data
        try:
            task, created = enqueue_attempt_run(
                request.user, pk, values['attempt_id'], item_id,
                values['code'], values['stdin'], request.headers.get('Idempotency-Key'),
            )
        except AIQuizServiceError as exc:
            return _error(exc)
        except ExecutionRequestError as exc:
            return Response({'error': exc.message, 'code': exc.code}, status=exc.status_code)
        data = public_task_data(task)
        data['created'] = created
        return Response(data, status=status.HTTP_202_ACCEPTED)


class AIQuizProgrammingSubmitView(APIView):
    permission_classes = [IsStudent]

    def post(self, request, pk, item_id):
        unavailable = _execution_unavailable()
        if unavailable:
            return unavailable
        serializer = AIQuizSubmitSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        values = serializer.validated_data
        try:
            task, submission, created = enqueue_attempt_grade(
                request.user, pk, values['attempt_id'], item_id,
                values['code'], request.headers.get('Idempotency-Key'),
            )
        except AIQuizServiceError as exc:
            return _error(exc)
        except ExecutionRequestError as exc:
            return Response({'error': exc.message, 'code': exc.code}, status=exc.status_code)
        data = public_task_data(task)
        data.update({'submission_id': submission.pk, 'created': created})
        return Response(data, status=status.HTTP_202_ACCEPTED)


class AIQuizProgrammingActiveExecutionView(APIView):
    permission_classes = [IsStudent]

    def get(self, request, pk, item_id):
        serializer = AIQuizActiveExecutionSerializer(data=request.query_params)
        if not serializer.is_valid():
            return _invalid(serializer)
        values = serializer.validated_data
        try:
            task = active_attempt_execution(
                request.user, pk, values['attempt_id'], item_id, values['task_type'],
            )
        except AIQuizServiceError as exc:
            return _error(exc)
        if task is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(public_task_data(task))
