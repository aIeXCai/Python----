from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Question, QuizSession, QuizSubmission
from .permissions import IsStudent
from .quiz_services import (
    QuizServiceError,
    SETTLED_STATUSES,
    attempt_student_payload,
    get_current_attempt,
    save_answers,
    start_or_resume_attempt,
    submit_attempt,
)
from .quiz_snapshot import result_payload
from .serializers import QuizAttemptAnswersSerializer


def quiz_error_response(exc):
    return Response(
        {'error': exc.message, 'code': exc.code, **exc.extra},
        status=exc.http_status,
    )


def _student_can_access_session(user, session):
    grades = session.visible_grades or []
    classes = {str(value) for value in (session.visible_classes or [])}
    return (not grades or user.grade in grades) and (
        not classes or str(user.class_num or '') in classes
    )


class QuizListView(APIView):
    """Current student's visible quizzes and one effective attempt per quiz."""
    permission_classes = [IsStudent]

    def get(self, request):
        sessions = QuizSession.objects.filter(
            status=QuizSession.STATUS_OPEN,
            archived_at__isnull=True,
        ).prefetch_related('units').order_by('-created_at')
        result = []
        for session in sessions:
            attempt = QuizSubmission.objects.filter(
                user=request.user, session=session, current_marker=True,
            ).first()
            can_start_new = _student_can_access_session(request.user, session)
            if not can_start_new and not (
                attempt and attempt.status == QuizSubmission.STATUS_IN_PROGRESS
            ):
                continue
            latest_settled = QuizSubmission.objects.filter(
                user=request.user, session=session, status__in=SETTLED_STATUSES,
            ).order_by('-attempt_no', '-id').first()
            if attempt and attempt.status == QuizSubmission.STATUS_IN_PROGRESS:
                try:
                    attempt = get_current_attempt(request.user, session.pk)
                except QuizServiceError:
                    pass

            if not attempt:
                action = 'start' if session.status == QuizSession.STATUS_OPEN else 'none'
                attempt_status = 'not_started'
            elif attempt.status == QuizSubmission.STATUS_IN_PROGRESS:
                action = 'continue'
                attempt_status = attempt.status
            elif attempt.status in SETTLED_STATUSES or attempt.snapshot_version == 0:
                action = 'restart'
                attempt_status = attempt.status
            else:
                action = 'none'
                attempt_status = attempt.status

            result.append({
                'id': session.id,
                'title': session.title,
                'unit_names': [unit.display_name for unit in session.units.all()],
                'num_questions': session.num_questions,
                'time_limit': session.time_limit,
                'status': session.status,
                'is_visible': session.status == QuizSession.STATUS_OPEN,
                'attempt_status': attempt_status,
                'action': action,
                'score': latest_settled.score if latest_settled else None,
                'best_score': latest_settled.score if latest_settled else None,
                'submitted': bool(latest_settled),
                'latest_submission_id': (
                    attempt.pk if attempt else latest_settled.pk if latest_settled else None
                ),
            })
        return Response(result)


class QuizDetailView(APIView):
    """Public metadata only; a GET never creates or redraws a paper."""
    permission_classes = [IsStudent]

    def get(self, request, pk):
        try:
            session = QuizSession.objects.get(pk=pk, archived_at__isnull=True)
        except QuizSession.DoesNotExist:
            return Response({'error': '小测不存在', 'code': 'quiz_not_found'}, status=404)
        has_attempt = QuizSubmission.objects.filter(
            user=request.user, session=session, current_marker=True,
        ).exists()
        if session.status != QuizSession.STATUS_OPEN and not has_attempt:
            return Response({'error': '小测不存在', 'code': 'quiz_not_found'}, status=404)
        if not _student_can_access_session(request.user, session) and not has_attempt:
            return Response({'error': '无权限访问该小测', 'code': 'quiz_grade_forbidden'}, status=403)
        return Response({
            'session_id': session.pk,
            'title': session.title,
            'num_questions': session.num_questions,
            'time_limit': session.time_limit,
            'status': session.status,
        })


class QuizAttemptView(APIView):
    permission_classes = [IsStudent]

    def post(self, request, pk):
        try:
            attempt, created = start_or_resume_attempt(request.user, pk)
            return Response(attempt_student_payload(attempt, created=created), status=201 if created else 200)
        except QuizServiceError as exc:
            return quiz_error_response(exc)

    def get(self, request, pk):
        try:
            attempt = get_current_attempt(request.user, pk)
            if attempt.status in SETTLED_STATUSES:
                raise QuizServiceError(
                    'attempt_completed', '本次小测已经完成', 409,
                    attempt_id=attempt.pk, result_available=True,
                )
            return Response(attempt_student_payload(attempt))
        except QuizServiceError as exc:
            return quiz_error_response(exc)


class QuizAttemptAnswersView(APIView):
    permission_classes = [IsStudent]

    def put(self, request, pk):
        serializer = QuizAttemptAnswersSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': '答案格式不正确', 'code': 'invalid_answers', 'details': serializer.errors},
                status=400,
            )
        data = serializer.validated_data
        try:
            attempt = save_answers(
                request.user, pk, data['attempt_id'], data['revision'], data['answers'],
            )
            payload = attempt_student_payload(attempt)
            return Response({
                'attempt_id': attempt.pk,
                'status': attempt.status,
                'revision': attempt.answer_revision,
                'saved_answers': attempt.answers,
                'server_time': payload['server_time'],
                'deadline_at': attempt.deadline_at,
                'remaining_seconds': payload['remaining_seconds'],
            })
        except QuizServiceError as exc:
            return quiz_error_response(exc)


class QuizAttemptSubmitView(APIView):
    permission_classes = [IsStudent]

    def post(self, request, pk):
        serializer = QuizAttemptAnswersSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': '答案格式不正确', 'code': 'invalid_answers', 'details': serializer.errors},
                status=400,
            )
        data = serializer.validated_data
        try:
            attempt = submit_attempt(
                request.user, pk, data['attempt_id'], data['revision'], data['answers'],
            )
            return Response({
                'attempt_id': attempt.pk,
                'submission_id': attempt.pk,
                'status': attempt.status,
                'score': attempt.score,
                'correct_count': attempt.correct_count,
                'total_count': attempt.total_count,
                'submitted_at': attempt.submitted_at,
                'result_url': f'/api/info/quizzes/{pk}/result/',
            })
        except QuizServiceError as exc:
            return quiz_error_response(exc)


class LegacyQuizSubmitView(APIView):
    permission_classes = [IsStudent]

    def post(self, request, pk):
        return Response({
            'error': '小测接口已升级，请刷新页面后重新进入',
            'code': 'quiz_api_upgraded',
        }, status=410)


def _legacy_result_payload(attempt):
    base = {
        'submission_id': attempt.pk,
        'attempt_id': attempt.pk,
        'quiz_title': attempt.session.title,
        'status': attempt.status,
        'score': attempt.score,
        'correct_count': attempt.correct_count,
        'total_count': attempt.total_count,
        'submitted_at': attempt.submitted_at,
        'question_results': [],
        'legacy_record': True,
        'analysis_available': False,
        'can_retry': attempt.session.status == QuizSession.STATUS_OPEN,
    }
    raw = attempt.answers
    answers = raw.get('answers', raw) if isinstance(raw, dict) else {}
    shuffled = raw.get('shuffled', {}) if isinstance(raw, dict) else {}
    orders = raw.get('shuffled_orders', {}) if isinstance(raw, dict) else {}
    details = []
    try:
        for qid, user_answer in answers.items():
            question = Question.objects.get(pk=int(qid))
            if attempt.submitted_at and question.updated_at > attempt.submitted_at:
                return base
            order = orders.get(str(qid))
            display_user = shuffled.get(str(qid)) or user_answer
            source_options = {
                'A': question.option_a, 'B': question.option_b,
                'C': question.option_c, 'D': question.option_d,
            }
            if order and len(order) == 4:
                options_text = {
                    chr(65 + index): source_options[source]
                    for index, source in enumerate(order)
                }
                correct_display = chr(65 + order.index(question.answer.upper()))
            else:
                options_text = source_options
                correct_display = question.answer.upper()
            if str(user_answer).upper() == question.answer.upper():
                continue
            details.append({
                'question_id': question.pk,
                'text': question.text,
                'user_answer': display_user or None,
                'correct_answer': correct_display,
                'is_correct': False,
                'explanation': question.explanation,
                'options': {
                    letter: {
                        'text': text,
                        'is_user_answer': display_user == letter,
                        'is_correct_answer': correct_display == letter,
                    }
                    for letter, text in options_text.items()
                },
            })
    except (Question.DoesNotExist, TypeError, ValueError, KeyError):
        return base
    base['question_results'] = details
    base['analysis_available'] = True
    return base


class QuizResultView(APIView):
    permission_classes = [IsStudent]

    def get(self, request, pk):
        try:
            attempt = get_current_attempt(request.user, pk)
        except QuizServiceError as exc:
            return quiz_error_response(exc)
        if attempt.status not in SETTLED_STATUSES and attempt.snapshot_version != 0:
            return Response(
                {'error': '本次小测尚未提交', 'code': 'attempt_in_progress'}, status=409,
            )
        if attempt.snapshot_version == 1:
            return Response(result_payload(attempt))
        return Response(_legacy_result_payload(attempt))
