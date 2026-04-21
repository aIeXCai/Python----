from rest_framework import serializers
from .models import CustomUser


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'role', 'grade', 'class_num', 'student_number']
        read_only_fields = ['id']


class LoginSerializer(serializers.Serializer):
    """登录请求：用户名 + 密码 + 年级 + 班级"""
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, write_only=True)
    grade = serializers.CharField(max_length=10, required=False)
    class_num = serializers.CharField(max_length=20, required=False)
