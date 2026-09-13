"""Teacher-facing API for AI quiz drafts and publication lifecycle."""

from django.conf import settings
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsTeacher
from users.scopes import TeacherScopeError, require_teacher_grade

from .models import (
    AUDIENCE_ALL_SCHOOL,
    AUDIENCE_CLASS,
    AUDIENCE_GRADE_ALL,
    AIQuizSession,
)
from .quiz_services import (
    AIQuizServiceError,
    close_quiz,
    copy_quiz,
    create_quiz,
    delete_quiz,
    publish_quiz,
    reopen_quiz,
    scoped_quizzes,
    update_quiz,
    update_quiz_audience,
    validate_quiz,
)
from .serializers_quizzes import (
    AIQuizAttemptResetSerializer,
    AIQuizAudienceUpdateSerializer,
    AIQuizCopySerializer,
    AIQuizSessionSerializer,
    AIQuizUpdateSerializer,
    AIQuizVersionSerializer,
    AIQuizWriteSerializer,
)
from .quiz_settlement_services import regrade_quiz_item, reset_attempt
from .quiz_analytics import (
    quiz_item_analysis,
    quiz_overview,
    quiz_students,
    student_attempts,
)
from execution.serializers import public_task_data
from execution.services import ExecutionRequestError


def _source_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    return (forwarded.split(',', 1)[0].strip() if forwarded else request.META.get('REMOTE_ADDR')) or None


def _error(exc):
    data = {'error': exc.message, 'code': exc.code}
    if exc.current_version is not None:
        data['management_version'] = exc.current_version
    if exc.details is not None:
        data['details'] = exc.details
    data.update(exc.extra)
    return Response(data, status=exc.status_code)


def _invalid(serializer):
    return Response(
        {'error': '参数错误', 'code': 'validation_error', 'details': serializer.errors},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _fresh(session_id):
    return AIQuizSession.objects.select_related('created_by').prefetch_related(
        'choice_units', 'programming_items__problem', 'audience_rules',
    ).get(pk=session_id)


class AdminAIQuizListView(APIView):
    permission_classes = [IsTeacher]

    def get(self, request):
        include_archived = request.query_params.get('include_archived') == '1'
        quizzes = scoped_quizzes(request.user, include_archived=include_archived)
        grade = request.query_params.get('grade')
        if grade:
            try:
                grade = require_teacher_grade(request.user, grade)
            except TeacherScopeError as exc:
                status_code = 400 if exc.code == 'invalid_grade' else 403
                return _error(AIQuizServiceError(
                    exc.message, code=exc.code, status_code=status_code,
                ))
            quizzes = quizzes.filter(content_grade=grade)
        class_num = (request.query_params.get('class_num') or '').strip()
        if class_num:
            audience = Q(
                audience_rules__is_active=True,
                audience_rules__scope_type=AUDIENCE_ALL_SCHOOL,
            )
            grade_scope = {
                'audience_rules__is_active': True,
                'audience_rules__scope_type': AUDIENCE_GRADE_ALL,
            }
            class_scope = {
                'audience_rules__is_active': True,
                'audience_rules__scope_type': AUDIENCE_CLASS,
                'audience_rules__class_num': class_num,
            }
            if grade:
                grade_scope['audience_rules__grade'] = grade
                class_scope['audience_rules__grade'] = grade
            audience |= Q(**grade_scope) | Q(**class_scope)
            quizzes = quizzes.filter(audience).distinct()
        status_filter = request.query_params.get('status')
        if status_filter:
            if status_filter not in dict(AIQuizSession.STATUS_CHOICES):
                return _error(AIQuizServiceError('小测状态筛选无效', code='invalid_status'))
            quizzes = quizzes.filter(status=status_filter)
        query = (request.query_params.get('q') or '').strip()
        if query:
            quizzes = quizzes.filter(Q(title__icontains=query))
        return Response(AIQuizSessionSerializer(quizzes, many=True).data)

    def post(self, request):
        serializer = AIQuizWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        try:
            session = create_quiz(
                actor=request.user,
                values=serializer.validated_data,
                source_ip=_source_ip(request),
            )
            return Response(
                AIQuizSessionSerializer(_fresh(session.pk)).data,
                status=status.HTTP_201_CREATED,
            )
        except AIQuizServiceError as exc:
            return _error(exc)


class AdminAIQuizDetailView(APIView):
    permission_classes = [IsTeacher]

    def get(self, request, pk):
        try:
            session = scoped_quizzes(request.user, include_archived=True).get(pk=pk)
        except AIQuizSession.DoesNotExist:
            return _error(AIQuizServiceError(
                '小测不存在', code='quiz_not_found', status_code=404,
            ))
        return Response(AIQuizSessionSerializer(session).data)

    def patch(self, request, pk):
        serializer = AIQuizUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        values = dict(serializer.validated_data)
        expected_version = values.pop('expected_version')
        try:
            session = update_quiz(
                actor=request.user,
                session_id=pk,
                values=values,
                expected_version=expected_version,
                source_ip=_source_ip(request),
            )
            return Response(AIQuizSessionSerializer(_fresh(session.pk)).data)
        except AIQuizServiceError as exc:
            return _error(exc)

    def delete(self, request, pk):
        serializer = AIQuizVersionSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        try:
            result = delete_quiz(
                actor=request.user,
                session_id=pk,
                expected_version=serializer.validated_data['expected_version'],
                source_ip=_source_ip(request),
            )
            return Response(result)
        except AIQuizServiceError as exc:
            return _error(exc)


class AdminAIQuizValidateView(APIView):
    permission_classes = [IsTeacher]

    def post(self, request, pk):
        serializer = AIQuizVersionSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        try:
            return Response(validate_quiz(
                actor=request.user,
                session_id=pk,
                expected_version=serializer.validated_data['expected_version'],
            ))
        except AIQuizServiceError as exc:
            return _error(exc)


class AdminAIQuizPublishView(APIView):
    permission_classes = [IsTeacher]

    def post(self, request, pk):
        serializer = AIQuizVersionSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        try:
            session = publish_quiz(
                actor=request.user,
                session_id=pk,
                expected_version=serializer.validated_data['expected_version'],
                source_ip=_source_ip(request),
            )
            return Response(AIQuizSessionSerializer(_fresh(session.pk)).data)
        except AIQuizServiceError as exc:
            return _error(exc)


class AdminAIQuizCloseView(APIView):
    permission_classes = [IsTeacher]

    def post(self, request, pk):
        serializer = AIQuizVersionSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        try:
            session = close_quiz(
                actor=request.user, session_id=pk,
                expected_version=serializer.validated_data['expected_version'],
                source_ip=_source_ip(request),
            )
            return Response(AIQuizSessionSerializer(_fresh(session.pk)).data)
        except AIQuizServiceError as exc:
            return _error(exc)


class AdminAIQuizReopenView(APIView):
    permission_classes = [IsTeacher]

    def post(self, request, pk):
        serializer = AIQuizVersionSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        try:
            session = reopen_quiz(
                actor=request.user, session_id=pk,
                expected_version=serializer.validated_data['expected_version'],
                source_ip=_source_ip(request),
            )
            return Response(AIQuizSessionSerializer(_fresh(session.pk)).data)
        except AIQuizServiceError as exc:
            return _error(exc)


class AdminAIQuizCopyView(APIView):
    permission_classes = [IsTeacher]

    def post(self, request, pk):
        serializer = AIQuizCopySerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        try:
            session = copy_quiz(
                actor=request.user, session_id=pk,
                title=serializer.validated_data.get('title'),
                source_ip=_source_ip(request),
            )
            return Response(
                AIQuizSessionSerializer(_fresh(session.pk)).data,
                status=status.HTTP_201_CREATED,
            )
        except AIQuizServiceError as exc:
            return _error(exc)


class AdminAIQuizAudienceView(APIView):
    permission_classes = [IsTeacher]

    def get(self, request, pk):
        try:
            session = scoped_quizzes(request.user, include_archived=True).get(pk=pk)
        except AIQuizSession.DoesNotExist:
            return _error(AIQuizServiceError(
                '小测不存在', code='quiz_not_found', status_code=404,
            ))
        data = AIQuizSessionSerializer(session).data
        return Response({
            'id': session.pk,
            'management_version': session.management_version,
            'audience': data['audience'],
        })

    def patch(self, request, pk):
        serializer = AIQuizAudienceUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        try:
            session = update_quiz_audience(
                actor=request.user,
                session_id=pk,
                audience=serializer.validated_data['audience'],
                expected_version=serializer.validated_data['expected_version'],
                source_ip=_source_ip(request),
            )
            return Response(AIQuizSessionSerializer(_fresh(session.pk)).data)
        except AIQuizServiceError as exc:
            return _error(exc)


class AdminAIQuizAttemptResetView(APIView):
    permission_classes = [IsTeacher]

    def post(self, request, pk, attempt_id):
        serializer = AIQuizAttemptResetSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        try:
            attempt = reset_attempt(
                actor=request.user,
                session_id=pk,
                attempt_id=attempt_id,
                reason=serializer.validated_data['reason'],
            )
            return Response({
                'attempt_id': attempt.pk,
                'status': attempt.status,
                'reset_at': attempt.reset_at,
            })
        except AIQuizServiceError as exc:
            return _error(exc)


class AdminAIQuizItemRegradeView(APIView):
    permission_classes = [IsTeacher]

    def post(self, request, pk, attempt_id, item_id):
        if not getattr(settings, 'CODE_EXECUTION_ENABLED', False):
            return Response(
                {'error': '代码执行服务暂不可用，请稍后重试'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        try:
            task, submission, created = regrade_quiz_item(
                actor=request.user,
                session_id=pk,
                attempt_id=attempt_id,
                item_id=item_id,
                idempotency_key=request.headers.get('Idempotency-Key'),
            )
        except AIQuizServiceError as exc:
            return _error(exc)
        except ExecutionRequestError as exc:
            return Response({'error': exc.message, 'code': exc.code}, status=exc.status_code)
        data = public_task_data(task)
        data.update({'submission_id': submission.pk, 'created': created})
        return Response(data, status=status.HTTP_202_ACCEPTED)


class AdminAIQuizAnalyticsOverviewView(APIView):
    permission_classes = [IsTeacher]

    def get(self, request, pk):
        try:
            return Response(quiz_overview(request.user, pk))
        except AIQuizServiceError as exc:
            return _error(exc)


class AdminAIQuizAnalyticsStudentsView(APIView):
    permission_classes = [IsTeacher]

    def get(self, request, pk):
        try:
            grade = request.query_params.get('grade', '')
            if grade:
                grade = require_teacher_grade(request.user, grade)
            return Response(quiz_students(
                request.user, pk,
                page=request.query_params.get('page', 1),
                page_size=request.query_params.get('page_size', 20),
                grade=grade,
                class_num=request.query_params.get('class_num', ''),
                status=request.query_params.get('status', ''),
                query=request.query_params.get('q', ''),
            ))
        except TeacherScopeError as exc:
            status_code = 400 if exc.code == 'invalid_grade' else 403
            return _error(AIQuizServiceError(
                exc.message, code=exc.code, status_code=status_code,
            ))
        except AIQuizServiceError as exc:
            return _error(exc)


class AdminAIQuizAnalyticsStudentAttemptsView(APIView):
    permission_classes = [IsTeacher]

    def get(self, request, pk, student_id):
        try:
            return Response(student_attempts(
                request.user, pk, student_id,
                page=request.query_params.get('page', 1),
                page_size=request.query_params.get('page_size', 10),
            ))
        except AIQuizServiceError as exc:
            return _error(exc)


class AdminAIQuizAnalyticsItemsView(APIView):
    permission_classes = [IsTeacher]

    def get(self, request, pk):
        try:
            return Response(quiz_item_analysis(request.user, pk))
        except AIQuizServiceError as exc:
            return _error(exc)
