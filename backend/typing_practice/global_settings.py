from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError as APIValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsTeacher

from .activities import (
    TRIAL_GRADES, language_snapshot, managed_grades, ordered_difficulties, practice_settings,
)
from .article_pool import require_article_pool
from .models import ArticleMode, GRADE_LABELS, Language, TypingPracticeSettings


class GlobalSettingsSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=ArticleMode.values)
    pinyin = serializers.BooleanField()
    fixed_articles = serializers.DictField(
        child=serializers.DictField(child=serializers.IntegerField(min_value=1)), default=dict,
    )

    def validate(self, data):
        fixed = data['fixed_articles']
        if data['mode'] == ArticleMode.FIXED:
            if set(fixed) != {str(grade) for grade in TRIAL_GRADES} or any(
                set(by_language) != set(Language.values) for by_language in fixed.values()
            ):
                raise serializers.ValidationError('请为各年级分别选择中英文固定文章。')
        elif fixed:
            raise serializers.ValidationError('固定文章仅在固定模式下使用。')
        return data


def settings_data(config):
    return {
        'mode': config.mode if config else ArticleMode.RANDOM,
        'pinyin': config.pinyin if config else False,
        'fixed_articles': config.fixed_articles if config else {},
    }


def article_choices(grade, language, pinyin):
    options = []
    for difficulty in ordered_difficulties(grade, language):
        try:
            pool = require_article_pool(
                grade=grade, language=language, difficulty=difficulty, pinyin=pinyin,
            )
        except ValidationError as exc:
            if exc.code != 'empty_article_pool':
                raise
            continue
        options.extend({'id': article.pk, 'title': article.title} for article in pool)
    return options


def snapshot_for(grade, language, mode, pinyin, revision_id):
    for difficulty in ordered_difficulties(grade, language):
        try:
            snapshot = language_snapshot(grade, language, {
                'mode': mode, 'difficulty': difficulty, 'pinyin': pinyin, 'article_id': revision_id,
            }, peak=None)
        except APIValidationError as exc:
            if exc.get_codes() not in (['empty_article_pool'], ['article_out_of_scope']):
                raise
        else:
            snapshot.pop('peak')
            return snapshot
    raise APIValidationError(f'{GRADE_LABELS[grade]}{Language(language).label}没有符合当前设置的文章。')


@transaction.atomic
def save_practice_settings(data):
    pools = {
        str(grade): {
            language: snapshot_for(
                grade, language, data['mode'], language == Language.CHINESE and data['pinyin'],
                data['fixed_articles'].get(str(grade), {}).get(language),
            )
            for language in Language.values
        }
        for grade in TRIAL_GRADES
    }
    row, _ = TypingPracticeSettings.objects.get_or_create(is_trial=not settings.TYPING_PRACTICE_FORMAL)
    row = TypingPracticeSettings.objects.select_for_update().get(pk=row.pk)
    if row.pools == pools and settings_data(row) == data:
        return row
    row.revision += 1
    row.mode, row.pinyin, row.fixed_articles = data['mode'], data['pinyin'], data['fixed_articles']
    row.pools = pools
    row.save(update_fields=['revision', 'mode', 'pinyin', 'fixed_articles', 'pools'])
    return row


def authorize_teacher(teacher):
    if not managed_grades(teacher):
        raise PermissionDenied('当前账号没有打字训练管理权限。')


class TeacherGlobalSettingsView(APIView):
    permission_classes = [IsTeacher]

    def get(self, request):
        authorize_teacher(request.user)
        return Response(settings_data(practice_settings()))

    def post(self, request):
        authorize_teacher(request.user)
        serializer = GlobalSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(settings_data(save_practice_settings(serializer.validated_data)))


class TeacherGlobalArticlesView(APIView):
    permission_classes = [IsTeacher]

    def get(self, request):
        authorize_teacher(request.user)
        query = serializers.BooleanField().run_validation(request.query_params.get('pinyin', 'false'))
        return Response([
            {
                'grade': grade, 'label': GRADE_LABELS[grade],
                'articles': {language: article_choices(grade, language, language == Language.CHINESE and query)
                             for language in Language.values},
            }
            for grade in TRIAL_GRADES
        ])
