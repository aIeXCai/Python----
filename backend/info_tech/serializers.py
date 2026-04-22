from rest_framework import serializers
from .models import Unit, Question


class UnitSerializer(serializers.ModelSerializer):
    question_count = serializers.IntegerField(source='questions.count', read_only=True)

    class Meta:
        model = Unit
        fields = ['id', 'name', 'display_name', 'order', 'question_count']


class QuestionSerializer(serializers.ModelSerializer):
    unit_name = serializers.CharField(source='unit.display_name', read_only=True)

    class Meta:
        model = Question
        fields = [
            'id', 'unit', 'unit_name', 'difficulty', 'category',
            'text', 'answer', 'explanation',
            'option_a', 'option_b', 'option_c', 'option_d',
            'created_at', 'updated_at'
        ]


class QuestionCreateSerializer(serializers.Serializer):
    """新增/编辑单题"""
    unit = serializers.CharField()           # 传单元 name，如 "第四单元"
    difficulty = serializers.ChoiceField(choices=['easy', 'medium', 'hard'], default='easy')
    category = serializers.CharField(required=False, default='', allow_blank=True)
    text = serializers.CharField()
    option_a = serializers.CharField()
    option_b = serializers.CharField()
    option_c = serializers.CharField()
    option_d = serializers.CharField()
    answer = serializers.ChoiceField(choices=['A', 'B', 'C', 'D'])
    explanation = serializers.CharField(required=False, default='', allow_blank=True)

    def validate_unit(self, value):
        try:
            unit = Unit.objects.get(name=value)
            return unit
        except Unit.DoesNotExist:
            raise serializers.ValidationError(f"单元 '{value}' 不存在，请先创建单元")

    def create(self, validated_data):
        unit = validated_data.pop('unit')
        return Question.objects.create(unit=unit, **validated_data)

    def update(self, instance, validated_data):
        unit = validated_data.pop('unit')
        validated_data['unit'] = unit
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        return instance


class QuestionImportSerializer(serializers.Serializer):
    """批量导入 JSON"""
    unit = serializers.CharField()               # 单元 name
    unit_display_name = serializers.CharField(required=False, default='')
    questions = serializers.ListField(child=serializers.DictField())

    def validate_questions(self, value):
        if not value:
            raise serializers.ValidationError("题目列表不能为空")
        return value

    def validate(self, data):
        unit_name = data['unit']
        unit_display = data.get('unit_display_name', '')

        # 单元不存在则自动创建
        unit, created = Unit.objects.get_or_create(
            name=unit_name,
            defaults={'display_name': unit_display or unit_name}
        )
        data['unit'] = unit
        data['unit_created'] = created
        return data

    def create(self, validated_data):
        unit = validated_data['unit']
        imported = 0
        errors = []

        for i, q in enumerate(validated_data['questions']):
            try:
                opts = q.get('options', [])
                opt_map = {}
                for o in opts:
                    key = o.get('key', '').upper()
                    if key in ('A', 'B', 'C', 'D'):
                        opt_map[key] = o.get('text', '')

                Question.objects.create(
                    unit=unit,
                    difficulty=q.get('difficulty', 'easy'),
                    category=q.get('category', ''),
                    text=q.get('text', ''),
                    answer=q.get('answer', 'A'),
                    explanation=q.get('explanation', ''),
                    option_a=opt_map.get('A', ''),
                    option_b=opt_map.get('B', ''),
                    option_c=opt_map.get('C', ''),
                    option_d=opt_map.get('D', ''),
                )
                imported += 1
            except Exception as e:
                errors.append(f"第{i+1}题: {str(e)}")

        return {'imported': imported, 'errors': errors}
