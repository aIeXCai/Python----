"""Teacher-facing APIs for AI units and choice questions."""

from django.db.models import Count, Prefetch, Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsTeacher
from users.scopes import TeacherScopeError, require_teacher_grade

from .models import AIChoiceQuestion
from .question_bank_services import (
    QuestionBankError,
    archive_unit,
    bulk_delete_choice_questions,
    copy_choice_question,
    create_choice_question,
    create_unit,
    delete_choice_question,
    delete_empty_unit,
    import_choice_questions,
    resolve_import_unit,
    restore_choice_question,
    restore_unit,
    scoped_choice_questions,
    scoped_units,
    update_choice_question,
    update_unit,
)
from .serializers_question_bank import (
    AIChoiceQuestionBulkDeleteSerializer,
    AIChoiceQuestionCreateSerializer,
    AIChoiceQuestionCopySerializer,
    AIChoiceQuestionImportSerializer,
    AIChoiceQuestionSerializer,
    AIChoiceQuestionUpdateSerializer,
    AIUnitSerializer,
    AIUnitWriteSerializer,
    ManagementVersionSerializer,
)


def _error(exc):
    data = {'error': exc.message, 'code': exc.code}
    if exc.current_version is not None:
        data['management_version'] = exc.current_version
    return Response(data, status=exc.status_code)


def _invalid(serializer):
    return Response(
        {'error': '参数错误', 'code': 'validation_error', 'details': serializer.errors},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _validate_requested_grade(request):
    grade = request.query_params.get('grade')
    if not grade:
        return None
    try:
        return require_teacher_grade(request.user, grade)
    except TeacherScopeError as exc:
        status_code = 400 if exc.code == 'invalid_grade' else 403
        raise QuestionBankError(exc.message, code=exc.code, status_code=status_code) from exc


class AdminAIUnitListView(APIView):
    permission_classes = [IsTeacher]

    def get(self, request):
        include_archived = request.query_params.get('include_archived') == '1'
        try:
            grade = _validate_requested_grade(request)
            units = scoped_units(
                request.user, include_archived=include_archived,
            ).filter(parent__isnull=True)
            if grade:
                units = units.filter(grade=grade)
            section_queryset = scoped_units(
                request.user, include_archived=include_archived,
            ).filter(parent__isnull=False).annotate(
                active_choice_question_count=Count(
                    'choice_questions',
                    filter=Q(choice_questions__archived_at__isnull=True),
                    distinct=True,
                ),
                active_programming_problem_count=Count(
                    'programming_problems',
                    filter=Q(programming_problems__archived_at__isnull=True),
                    distinct=True,
                ),
            ).order_by('order', 'id')
            units = units.annotate(
                active_choice_question_count=Count(
                    'choice_questions',
                    filter=Q(choice_questions__archived_at__isnull=True),
                    distinct=True,
                ),
                active_programming_problem_count=Count(
                    'programming_problems',
                    filter=Q(programming_problems__archived_at__isnull=True),
                    distinct=True,
                ),
            ).prefetch_related(
                Prefetch('sections', queryset=section_queryset),
            ).order_by('grade', 'order', 'id')
            data = AIUnitSerializer(
                units, many=True,
                context={'request': request, 'include_archived': include_archived},
            ).data
            return Response(data)
        except QuestionBankError as exc:
            return _error(exc)

    def post(self, request):
        serializer = AIUnitWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        try:
            unit = create_unit(actor=request.user, values=serializer.validated_data)
            return Response(
                AIUnitSerializer(unit, context={'request': request}).data,
                status=status.HTTP_201_CREATED,
            )
        except QuestionBankError as exc:
            return _error(exc)


class AdminAIUnitDetailView(APIView):
    permission_classes = [IsTeacher]

    def patch(self, request, pk):
        serializer = AIUnitWriteSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return _invalid(serializer)
        try:
            unit = update_unit(
                actor=request.user, unit_id=pk, values=serializer.validated_data,
            )
            return Response(AIUnitSerializer(unit, context={'request': request}).data)
        except QuestionBankError as exc:
            return _error(exc)

    def delete(self, request, pk):
        try:
            unit = archive_unit(actor=request.user, unit_id=pk)
            return Response(AIUnitSerializer(
                unit, context={'request': request, 'include_archived': True},
            ).data)
        except QuestionBankError as exc:
            return _error(exc)


class AdminAIUnitRestoreView(APIView):
    permission_classes = [IsTeacher]

    def post(self, request, pk):
        try:
            unit = restore_unit(actor=request.user, unit_id=pk)
            return Response(AIUnitSerializer(unit, context={'request': request}).data)
        except QuestionBankError as exc:
            return _error(exc)


class AdminAIUnitPermanentDeleteView(APIView):
    permission_classes = [IsTeacher]

    def delete(self, request, pk):
        try:
            delete_empty_unit(actor=request.user, unit_id=pk)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except QuestionBankError as exc:
            return _error(exc)


class AdminAIChoiceQuestionListView(APIView):
    permission_classes = [IsTeacher]

    def get(self, request):
        status_filter = request.query_params.get('status', 'active')
        include_archived = (
            request.query_params.get('include_archived') == '1'
            or status_filter == 'archived'
        )
        try:
            grade = _validate_requested_grade(request)
            questions = scoped_choice_questions(
                request.user, include_archived=include_archived,
            )
            if grade:
                questions = questions.filter(unit__grade=grade)
            if status_filter == 'archived':
                questions = questions.filter(
                    Q(archived_at__isnull=False)
                    | Q(unit__archived_at__isnull=False)
                    | Q(unit__parent__archived_at__isnull=False)
                )
            elif status_filter not in ('active', 'all'):
                raise QuestionBankError('题目状态筛选无效', code='invalid_status')
            big_unit = request.query_params.get('big_unit')
            if big_unit:
                questions = questions.filter(unit__parent_id=big_unit)
            big_unit_name = request.query_params.get('big_unit_name')
            if big_unit_name:
                questions = questions.filter(unit__parent__name=big_unit_name)
            unit = request.query_params.get('unit')
            if unit:
                questions = questions.filter(unit_id=unit)
            unit_name = request.query_params.get('unit_name')
            if unit_name:
                questions = questions.filter(unit__name=unit_name)
            difficulty = request.query_params.get('difficulty')
            if difficulty:
                if difficulty not in dict(AIChoiceQuestion.DIFFICULTY_CHOICES):
                    raise QuestionBankError('题目难度筛选无效', code='invalid_difficulty')
                questions = questions.filter(difficulty=difficulty)
            query = (request.query_params.get('q') or '').strip()
            if query:
                questions = questions.filter(
                    Q(text__icontains=query)
                    | Q(category__icontains=query)
                    | Q(option_a__icontains=query)
                    | Q(option_b__icontains=query)
                    | Q(option_c__icontains=query)
                    | Q(option_d__icontains=query)
                    | Q(explanation__icontains=query),
                )
            return Response(AIChoiceQuestionSerializer(
                questions.order_by('id'), many=True, context={'request': request},
            ).data)
        except QuestionBankError as exc:
            return _error(exc)

    def post(self, request):
        serializer = AIChoiceQuestionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        try:
            question = create_choice_question(
                actor=request.user, values=serializer.validated_data,
            )
            return Response(
                AIChoiceQuestionSerializer(question, context={'request': request}).data,
                status=status.HTTP_201_CREATED,
            )
        except QuestionBankError as exc:
            return _error(exc)


class AdminAIChoiceQuestionDetailView(APIView):
    permission_classes = [IsTeacher]

    def get(self, request, pk):
        try:
            question = scoped_choice_questions(
                request.user, include_archived=True,
            ).get(pk=pk)
        except AIChoiceQuestion.DoesNotExist:
            return _error(QuestionBankError(
                '选择题不存在', code='choice_question_not_found', status_code=404,
            ))
        return Response(AIChoiceQuestionSerializer(
            question, context={'request': request},
        ).data)

    def patch(self, request, pk):
        serializer = AIChoiceQuestionUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        values = dict(serializer.validated_data)
        expected_version = values.pop('expected_version')
        try:
            question = update_choice_question(
                actor=request.user,
                question_id=pk,
                values=values,
                expected_version=expected_version,
            )
            return Response(AIChoiceQuestionSerializer(
                question, context={'request': request},
            ).data)
        except QuestionBankError as exc:
            return _error(exc)

    def delete(self, request, pk):
        serializer = ManagementVersionSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        try:
            delete_choice_question(
                actor=request.user,
                question_id=pk,
                expected_version=serializer.validated_data['expected_version'],
            )
            return Response(status=status.HTTP_204_NO_CONTENT)
        except QuestionBankError as exc:
            return _error(exc)


class AdminAIChoiceQuestionBulkDeleteView(APIView):
    permission_classes = [IsTeacher]

    def post(self, request):
        serializer = AIChoiceQuestionBulkDeleteSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        try:
            deleted_count = bulk_delete_choice_questions(
                actor=request.user,
                items=serializer.validated_data['items'],
            )
            return Response({'deleted_count': deleted_count})
        except QuestionBankError as exc:
            return _error(exc)


class AdminAIChoiceQuestionRestoreView(APIView):
    permission_classes = [IsTeacher]

    def post(self, request, pk):
        serializer = ManagementVersionSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        try:
            question = restore_choice_question(
                actor=request.user,
                question_id=pk,
                expected_version=serializer.validated_data['expected_version'],
            )
            return Response(AIChoiceQuestionSerializer(
                question, context={'request': request},
            ).data)
        except QuestionBankError as exc:
            return _error(exc)


class AdminAIChoiceQuestionCopyView(APIView):
    permission_classes = [IsTeacher]

    def post(self, request, pk):
        serializer = AIChoiceQuestionCopySerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        try:
            question = copy_choice_question(
                actor=request.user,
                question_id=pk,
                unit_id=serializer.validated_data.get('unit'),
            )
            return Response(
                AIChoiceQuestionSerializer(question, context={'request': request}).data,
                status=status.HTTP_201_CREATED,
            )
        except QuestionBankError as exc:
            return _error(exc)


class AdminAIChoiceQuestionImportView(APIView):
    permission_classes = [IsTeacher]

    def post(self, request):
        serializer = AIChoiceQuestionImportSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        values = serializer.validated_data
        try:
            unit = resolve_import_unit(
                actor=request.user,
                unit_id=values.get('unit_id'),
                unit_name=values.get('unit', ''),
                grade=values.get('grade'),
            )
            questions = import_choice_questions(
                actor=request.user,
                unit_id=unit.pk,
                questions=values['questions'],
            )
            return Response({
                'detail': f'成功导入 {len(questions)} 题',
                'imported': len(questions),
                'unit_id': unit.pk,
                'question_ids': [question.pk for question in questions],
            }, status=status.HTTP_201_CREATED)
        except QuestionBankError as exc:
            return _error(exc)
