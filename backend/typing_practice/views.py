from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError as APIValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsStudent, IsTeacher

from .activities import (
    TRIAL_GRADES, close_activity, current_activity, managed_grades, publish_activity, require_class, start_attempt, student_activities,
    teacher_activities, trial_speed_rules,
)
from .article_pool import require_article_pool
from .models import ArticleMode, GRADE_LABELS, Language, TypingArticleRevision, TypingAttempt
from .serializers import ArticleOptionsSerializer, ClassSettingsSerializer, PublishActivitySerializer, StartAttemptSerializer


def article_summary(article):
    return {'id': article.pk, 'title': article.title, 'version': article.version}


def activity_data(activity, *, include_options=False, for_teacher=False):
    languages = {}
    for language, setup in activity.languages.items():
        languages[language] = {
            key: setup[key] for key in ('mode', 'difficulty', 'pinyin', 'peak')
        }
        if for_teacher and setup['mode'] == ArticleMode.FIXED:
            languages[language]['article_id'] = setup['article_ids'][0]
        if include_options and setup['mode'] == ArticleMode.FREE:
            candidates = TypingArticleRevision.objects.filter(pk__in=setup['article_ids']).order_by('title', 'pk')
            languages[language]['articles'] = [article_summary(article) for article in candidates]
    return {
        'id': activity.pk, 'title': activity.title, 'grade': activity.grade,
        'class_num': activity.class_num, 'languages': languages, 'published_at': activity.published_at,
        'closed_at': activity.closed_at, 'is_default': activity.teacher_id is None,
    }


def attempt_data(attempt):
    now = timezone.now()
    settings = attempt.activity.languages[attempt.language]
    article = attempt.first_article
    return {
        'id': attempt.pk, 'language': attempt.language, 'activity': activity_data(attempt.activity),
        'started_at': attempt.started_at, 'deadline_at': attempt.deadline_at, 'server_now': now,
        'expired': attempt.deadline_at <= now,
        'article': {
            **article_summary(article), 'paragraphs': article.paragraphs,
            'pinyin': article.pinyin if settings['pinyin'] else None,
        },
    }


class TeacherClassesView(APIView):
    permission_classes = [IsTeacher]

    def get(self, request):
        choices = []
        for grade in managed_grades(request.user):
            label = GRADE_LABELS[grade]
            classes = get_user_model().objects.filter(
                is_active=True, role='student', grade=label,
            ).exclude(class_num__isnull=True).exclude(class_num='').order_by('class_num')
            choices.append({
                'grade': grade, 'label': label,
                'classes': list(classes.values_list('class_num', flat=True).distinct()),
            })
        return Response(choices)


class TeacherArticlesView(APIView):
    permission_classes = [IsTeacher]

    def get(self, request):
        query = ArticleOptionsSerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        grade, language = data['grade'], data['language']
        require_class(request.user, grade, data['class_num'])
        if data['pinyin'] and language != Language.CHINESE:
            raise APIValidationError('英文练习不提供拼音。')
        difficulties = trial_speed_rules(grade, language).order_by('difficulty').values_list('difficulty', flat=True).distinct()
        options = []
        for difficulty in difficulties:
            try:
                pool = require_article_pool(grade=grade, language=language, difficulty=difficulty, pinyin=data['pinyin'])
            except ValidationError as exc:
                if exc.code != 'empty_article_pool':
                    raise
                continue
            options.append({'difficulty': difficulty, 'articles': [article_summary(article) for article in pool]})
        return Response(options)


class TeacherActivitiesView(APIView):
    permission_classes = [IsTeacher]

    def get(self, request):
        if request.query_params:
            query = ClassSettingsSerializer(data=request.query_params)
            query.is_valid(raise_exception=True)
            scope = query.validated_data
            require_class(request.user, **scope)
            activity = current_activity(**scope)
            return Response(activity_data(activity, for_teacher=True) if activity else None)
        activities = teacher_activities(request.user).order_by('-published_at', '-pk')[:50]
        return Response([activity_data(activity) for activity in activities])

    def post(self, request):
        body = PublishActivitySerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return Response(activity_data(publish_activity(request.user, body.validated_data), for_teacher=True), status=201)


class TeacherCloseActivityView(APIView):
    permission_classes = [IsTeacher]

    def post(self, request, activity_id):
        return Response(activity_data(close_activity(request.user, activity_id)))


class StudentActivitiesView(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        visible = student_activities(request.user)
        grade = next((number for number in TRIAL_GRADES if GRADE_LABELS[number] == request.user.grade), None)
        activity = current_activity(grade, request.user.class_num) if grade and request.user.class_num else None
        active = TypingAttempt.objects.filter(
            active_student=request.user, activity__in=visible, deadline_at__gt=timezone.now(),
        ).values_list('pk', flat=True).first()
        return Response({
            'activities': [activity_data(activity, include_options=True)] if activity else [],
            'active_attempt_id': active,
        })


class StudentAttemptsView(APIView):
    permission_classes = [IsStudent]

    def post(self, request):
        body = StartAttemptSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        attempt, created = start_attempt(request.user, body.validated_data)
        return Response(attempt_data(attempt), status=201 if created else 200)


class StudentAttemptView(APIView):
    permission_classes = [IsStudent]

    def get(self, request, attempt_id):
        attempt = TypingAttempt.objects.select_related('activity', 'first_article').filter(
            pk=attempt_id, student=request.user, activity__in=student_activities(request.user),
        ).first()
        if attempt is None:
            raise NotFound('没有找到该次练习。')
        return Response(attempt_data(attempt))
