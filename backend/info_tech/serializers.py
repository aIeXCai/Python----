from rest_framework import serializers
from .models import Unit, Question, QuizSession, QuizSubmission
from users.grade_levels import normalize_grade
from users.scopes import TeacherScopeError, require_teacher_grade, scope_by_grade


class UnitSerializer(serializers.ModelSerializer):
    question_count = serializers.IntegerField(source='questions.count', read_only=True)
    sections = serializers.SerializerMethodField()

    class Meta:
        model = Unit
        fields = ['id', 'grade', 'parent', 'name', 'display_name', 'order', 'question_count', 'sections']

    def get_sections(self, obj):
        # 只返回小节（parent 不为空）
        sections = obj.sections.all().order_by('order')
        return UnitSectionSerializer(sections, many=True).data


class UnitSectionSerializer(serializers.ModelSerializer):
    """小节的简化序列化（不含递归sections）"""
    question_count = serializers.IntegerField(source='questions.count', read_only=True)

    class Meta:
        model = Unit
        fields = ['id', 'grade', 'parent', 'name', 'display_name', 'order', 'question_count']


class QuestionSerializer(serializers.ModelSerializer):
    unit_name = serializers.CharField(source='unit.display_name', read_only=True)
    big_unit_name = serializers.SerializerMethodField()
    grade = serializers.CharField(source='unit.grade', read_only=True)

    class Meta:
        model = Question
        fields = [
            'id', 'unit', 'grade', 'unit_name', 'big_unit_name', 'difficulty', 'category',
            'text', 'answer', 'explanation',
            'option_a', 'option_b', 'option_c', 'option_d',
            'created_at', 'updated_at'
        ]

    def get_big_unit_name(self, obj):
        if obj.unit.parent:
            return obj.unit.parent.display_name
        return ''


class QuestionCreateSerializer(serializers.Serializer):
    """新增/编辑单题"""
    unit = serializers.CharField()           # 传单元 name，如 "第四单元"
    grade = serializers.CharField(required=False, write_only=True)
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
            units = Unit.objects.filter(name=value)
            grade = self.initial_data.get('grade')
            if grade:
                units = units.filter(grade=normalize_grade(grade))
            request = self.context.get('request')
            if request:
                units = scope_by_grade(units, request.user)
            unit = units.get()
            return unit
        except (Unit.DoesNotExist, Unit.MultipleObjectsReturned):
            raise serializers.ValidationError(f"单元 '{value}' 不存在，请先创建单元")

    def create(self, validated_data):
        unit = validated_data.pop('unit')
        validated_data.pop('grade', None)
        return Question.objects.create(unit=unit, **validated_data)

    def update(self, instance, validated_data):
        unit = validated_data.pop('unit')
        validated_data.pop('grade', None)
        validated_data['unit'] = unit
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        return instance


class QuestionImportSerializer(serializers.Serializer):
    """批量导入 JSON"""
    unit = serializers.CharField()                    # 单元 name（小节 name）
    unit_display_name = serializers.CharField(required=False, default='')
    grade = serializers.CharField(required=False, default='七年级')  # 用于唯一定位同名单元
    questions = serializers.ListField(child=serializers.DictField())

    def validate_questions(self, value):
        if not value:
            raise serializers.ValidationError("题目列表不能为空")
        return value

    def validate(self, data):
        unit_name = data['unit']
        unit_display = data.get('unit_display_name', '')
        try:
            grade = normalize_grade(data.get('grade', '七年级'))
            request = self.context.get('request')
            if request:
                require_teacher_grade(request.user, grade)
        except Exception as exc:
            raise serializers.ValidationError({'grade': str(exc)}) from exc
        data['grade'] = grade

        # 用 name + grade 唯一定位（解决七年级/八年级单元 name 相同的问题）
        unit, created = Unit.objects.update_or_create(
            name=unit_name,
            grade=grade,
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


# ─── QuizSession Serializers ──────────────────────────────────────────────────

class QuizSessionSerializer(serializers.ModelSerializer):
    """小测详情（完整，含关联单元）"""
    units = serializers.SerializerMethodField()
    unit_names = serializers.SerializerMethodField()
    big_unit_names = serializers.SerializerMethodField()
    section_names = serializers.SerializerMethodField()
    grade = serializers.SerializerMethodField()   # visible_grades[0] 或第一个单元的年级
    submission_count = serializers.SerializerMethodField()
    is_visible = serializers.SerializerMethodField()

    class Meta:
        model = QuizSession
        fields = [
            'id', 'title', 'created_by', 'units', 'unit_names', 'big_unit_names', 'section_names', 'grade',
            'num_questions', 'difficulty_ratio', 'time_limit',
            'status', 'is_visible', 'visible_grades', 'visible_classes', 'submission_count',
            'opened_at', 'closed_at', 'archived_at',
            'created_at', 'updated_at'
        ]

    def get_is_visible(self, obj):
        return obj.status == QuizSession.STATUS_OPEN

    def get_submission_count(self, obj):
        return obj.quizsubmission_set.filter(
            status__in=(QuizSubmission.STATUS_SUBMITTED, QuizSubmission.STATUS_TIMED_OUT),
        ).values('user_id').distinct().count()

    def get_units(self, obj):
        return [u.id for u in obj.units.all()]

    def get_unit_names(self, obj):
        return [u.display_name for u in obj.units.all()]

    def get_big_unit_names(self, obj):
        seen = set()
        result = []
        for u in obj.units.all():
            if u.parent and u.parent.id not in seen:
                seen.add(u.parent.id)
                result.append(u.parent.display_name)
        return result

    def get_section_names(self, obj):
        # 小节：所有非根单元（即 parent 不为空的）
        return [u.display_name for u in obj.units.all() if u.parent]

    def get_grade(self, obj):
        if obj.visible_grades:
            return obj.visible_grades[0]
        first_unit = obj.units.first()
        return first_unit.grade if first_unit else '七年级'


class QuizSessionCreateSerializer(serializers.Serializer):
    """创建/编辑小测"""
    title            = serializers.CharField(max_length=200)
    units            = serializers.ListField(child=serializers.IntegerField())  # [unit_id, ...]
    num_questions    = serializers.IntegerField(min_value=1)
    difficulty_ratio = serializers.JSONField(default=dict)   # {"easy":7,"medium":2,"hard":1}
    time_limit       = serializers.IntegerField(required=False, min_value=1, allow_null=True)
    is_visible       = serializers.BooleanField(default=False)
    visible_grades   = serializers.ListField(
        child=serializers.CharField(max_length=20), default=list,
    )
    visible_classes  = serializers.ListField(
        child=serializers.CharField(max_length=20, trim_whitespace=True), default=list,
    )  # [] = 所选年级全部班级

    def validate(self, attrs):
        ratio = attrs.get('difficulty_ratio') or {}
        num_questions = attrs.get('num_questions')
        if num_questions is not None:
            if not ratio:
                ratio = {'easy': num_questions}
                attrs['difficulty_ratio'] = ratio
            total = sum(int(v) for v in ratio.values() if isinstance(v, (int, float)) and v >= 0)
            if total > num_questions:
                raise serializers.ValidationError({'difficulty_ratio': '难度题数总和不能超过小测题数'})
        unit_ids = attrs.get('units', [])
        grades = set(Unit.objects.filter(id__in=unit_ids).values_list('grade', flat=True))
        visible_grades = attrs.get('visible_grades') or []
        visible_classes = attrs.get('visible_classes') or []
        if len(set(visible_classes)) != len(visible_classes) or any(not value for value in visible_classes):
            raise serializers.ValidationError({'visible_classes': '班级范围不能包含空值或重复值'})
        request = self.context.get('request')
        if request and not request.user.is_superuser:
            try:
                managed_grade = require_teacher_grade(request.user)
            except TeacherScopeError as exc:
                raise serializers.ValidationError({'code': exc.code, 'detail': exc.message}) from exc
            if grades - {managed_grade} or set(visible_grades) - {managed_grade}:
                raise serializers.ValidationError('不能管理其他年级的小测')
            if not visible_grades:
                attrs['visible_grades'] = [managed_grade]
        return attrs

    def validate_units(self, value):
        if not value:
            raise serializers.ValidationError("必须选择至少一个单元")
        units = Unit.objects.filter(id__in=value)
        request = self.context.get('request')
        if request:
            units = scope_by_grade(units, request.user)
        if units.count() != len(value):
            raise serializers.ValidationError("存在无效的单元ID")
        return value

    def validate_difficulty_ratio(self, value):
        if not value:
            return {}
        total = sum(v for v in value.values() if isinstance(v, (int, float)))
        if total == 0:
            raise serializers.ValidationError("难度比例总和不能为0")
        return value

    def create(self, validated_data):
        unit_ids = validated_data.pop('units')
        validated_data.pop('is_visible', False)
        session = QuizSession.objects.create(
            created_by=self.context['request'].user,
            **validated_data
        )
        session.units.set(unit_ids)
        return session

    def update(self, instance, validated_data):
        unit_ids = validated_data.pop('units', None)
        validated_data.pop('is_visible', False)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        if unit_ids is not None:
            instance.units.set(unit_ids)
        return instance


class QuizSessionToggleSerializer(serializers.Serializer):
    """切换可见性"""
    is_visible     = serializers.BooleanField()
    visible_grades  = serializers.JSONField(required=False, default=list)
    visible_classes = serializers.ListField(
        child=serializers.CharField(max_length=20, trim_whitespace=True), required=False,
    )


class QuizSessionStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=(QuizSession.STATUS_OPEN, QuizSession.STATUS_CLOSED))
    visible_grades = serializers.ListField(
        child=serializers.CharField(max_length=20), required=False,
    )
    visible_classes = serializers.ListField(
        child=serializers.CharField(max_length=20, trim_whitespace=True), required=False,
    )


class QuizAttemptAnswersSerializer(serializers.Serializer):
    attempt_id = serializers.IntegerField(min_value=1)
    revision = serializers.IntegerField(min_value=0)
    answers = serializers.DictField(
        child=serializers.ChoiceField(choices=('A', 'B', 'C', 'D'), allow_null=True),
        allow_empty=True,
    )


class QuizAttemptResetSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=300, allow_blank=False, trim_whitespace=True)
