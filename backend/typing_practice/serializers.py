from rest_framework import serializers

from .models import ArticleMode, Language


class LanguageSetupSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=ArticleMode.values)
    difficulty = serializers.CharField(max_length=30)
    article_id = serializers.IntegerField(min_value=1, required=False)
    pinyin = serializers.BooleanField(default=False)

    def validate(self, attrs):
        if (attrs['mode'] == ArticleMode.FIXED) != ('article_id' in attrs):
            raise serializers.ValidationError('固定模式需指定一篇文章。')
        return attrs


class PublishActivitySerializer(serializers.Serializer):
    title = serializers.CharField(max_length=100, default='打字训练')
    grade = serializers.IntegerField(min_value=3, max_value=8)
    class_num = serializers.CharField(max_length=20)
    zh = LanguageSetupSerializer()
    en = LanguageSetupSerializer()

    def validate_en(self, value):
        if value['pinyin']:
            raise serializers.ValidationError('英文练习不提供拼音。')
        return value


class ClassSettingsSerializer(serializers.Serializer):
    grade = serializers.IntegerField(min_value=3, max_value=8)
    class_num = serializers.CharField(max_length=20)


class ArticleOptionsSerializer(ClassSettingsSerializer):
    language = serializers.ChoiceField(choices=Language.values)
    pinyin = serializers.BooleanField(default=False)


class StartAttemptSerializer(serializers.Serializer):
    activity_id = serializers.IntegerField(min_value=1)
    language = serializers.ChoiceField(choices=Language.values)
    article_id = serializers.IntegerField(min_value=1, required=False)
