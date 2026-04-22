from rest_framework import serializers
from .models import CustomUser


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'role', 'grade', 'class_num', 'student_number', 'display_name']
        read_only_fields = ['id']


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
