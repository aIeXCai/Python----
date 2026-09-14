"""Student endpoints for visible AI quizzes and active choice-question attempts."""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsStudent

from .attempt_services import (
    attempt_student_payload,
    get_current_attempt,
    save_choice_answers,
    start_or_resume_attempt,
    student_quiz_list,
)
from .services import AIQuizServiceError
from .serializers_attempts import AIQuizAttemptAnswersSerializer
from .serializers_attempts import AIQuizAttemptSubmitSerializer
from .settlement_services import (
    get_student_result,
    request_settlement,
    student_attempt_history,
)


def _error(exc):
    data = {'error': exc.message, 'code': exc.code}
    if exc.current_version is not None:
        data['management_version'] = exc.current_version
    if exc.details is not None:
        data['details'] = exc.details
    data.update(exc.extra)
    return Response(data, status=exc.status_code)


class AIQuizListView(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        try:
            return Response(student_quiz_list(request.user))
        except AIQuizServiceError as exc:
            return _error(exc)


class AIQuizAttemptView(APIView):
    permission_classes = [IsStudent]

    def post(self, request, pk):
        try:
            attempt, created = start_or_resume_attempt(request.user, pk)
            return Response(
                attempt_student_payload(attempt, created=created),
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )
        except AIQuizServiceError as exc:
            return _error(exc)

    def get(self, request, pk):
        try:
            attempt = get_current_attempt(request.user, pk)
            return Response(attempt_student_payload(attempt))
        except AIQuizServiceError as exc:
            return _error(exc)


class AIQuizAttemptAnswersView(APIView):
    permission_classes = [IsStudent]

    def put(self, request, pk):
        serializer = AIQuizAttemptAnswersSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': '答案格式不正确',
                    'code': 'invalid_answers',
                    'details': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        values = serializer.validated_data
        try:
            attempt = save_choice_answers(
                request.user,
                pk,
                values['attempt_id'],
                values['revision'],
                values['answers'],
            )
            payload = attempt_student_payload(attempt)
            return Response({
                'attempt_id': attempt.pk,
                'status': attempt.status,
                'revision': attempt.answer_revision,
                'saved_answers': attempt.answers_json,
                'server_time': payload['server_time'],
                'deadline_at': attempt.deadline_at,
                'remaining_seconds': payload['remaining_seconds'],
            })
        except AIQuizServiceError as exc:
            return _error(exc)


class AIQuizAttemptSubmitView(APIView):
    permission_classes = [IsStudent]

    def post(self, request, pk):
        serializer = AIQuizAttemptSubmitSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': '答案格式不正确', 'code': 'invalid_answers', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        values = serializer.validated_data
        try:
            attempt = request_settlement(
                user=request.user,
                session_id=pk,
                attempt_id=values['attempt_id'],
                reason='submitted',
                final_answers=values['answers'],
                revision=values['revision'],
            )
            return Response(get_student_result(request.user, pk))
        except AIQuizServiceError as exc:
            return _error(exc)


class AIQuizResultView(APIView):
    permission_classes = [IsStudent]

    def get(self, request, pk):
        try:
            return Response(get_student_result(request.user, pk))
        except AIQuizServiceError as exc:
            return _error(exc)


class AIQuizAttemptHistoryView(APIView):
    permission_classes = [IsStudent]

    def get(self, request, pk):
        try:
            return Response(student_attempt_history(request.user, pk))
        except AIQuizServiceError as exc:
            return _error(exc)
