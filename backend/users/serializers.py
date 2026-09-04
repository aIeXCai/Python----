from rest_framework import serializers
from .models import CustomUser
from .grade_levels import normalize_grade, normalize_student_identifier


class UserSerializer(serializers.ModelSerializer):
    password_available = serializers.SerializerMethodField()

    def get_password_available(self, obj):
        return bool(
            obj.role == 'student'
            and obj.password_recovery_status == 'available'
            and obj.encrypted_password
            and obj.password_encryption_key_id
        )

    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'role', 'grade', 'class_num', 'student_number',
            'display_name', 'managed_grade', 'is_superuser', 'password_available',
        ]
        read_only_fields = ['id', 'managed_grade', 'is_superuser']


class LoginSerializer(serializers.Serializer):
    """
    登录请求：
    - 老师：username + password
    - 学生：grade + class_num + student_number + password
    """
    username = serializers.CharField(max_length=150, required=False)
    password = serializers.CharField(max_length=128, write_only=True)
    grade = serializers.CharField(max_length=10, required=False)
    class_num = serializers.CharField(max_length=20, required=False)
    student_number = serializers.CharField(max_length=20, required=False)

    def validate(self, attrs):
        supplied = any(attrs.get(key) not in (None, '') for key in (
            'grade', 'class_num', 'student_number',
        ))
        if supplied:
            try:
                attrs['grade'] = normalize_grade(attrs.get('grade'))
                attrs['class_num'] = normalize_student_identifier(
                    attrs.get('class_num'), label='班级',
                )
                attrs['student_number'] = normalize_student_identifier(
                    attrs.get('student_number'), label='班内学号',
                )
            except Exception as exc:
                raise serializers.ValidationError(str(exc)) from exc
        return attrs


class PasswordResetSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=['manual', 'generated'])
    password = serializers.CharField(
        max_length=128, required=False, allow_blank=False, write_only=True
    )

    def validate(self, attrs):
        if attrs['mode'] == 'manual' and not attrs.get('password'):
            raise serializers.ValidationError({'password': '手工重置必须提供新密码。'})
        if attrs['mode'] == 'generated' and 'password' in attrs:
            raise serializers.ValidationError({'password': '生成模式不能提交密码。'})
        return attrs
