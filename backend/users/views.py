from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate

from .models import CustomUser
from .serializers import UserSerializer, LoginSerializer


class LoginView(APIView):
    """学生/老师登录"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': '参数错误', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        username = serializer.validated_data['username']
        password = serializer.validated_data['password']
        grade = serializer.validated_data.get('grade')
        class_num = serializer.validated_data.get('class_num')

        # 先用 Django 默认方式验证密码
        user = authenticate(username=username, password=password)

        if not user:
            return Response(
                {'error': '用户名或密码错误'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # 如果提供了 grade/class_num，校验是否匹配
        if grade and class_num and user.role == 'student':
            if user.grade != grade or user.class_num != class_num:
                return Response(
                    {'error': '年级或班级不匹配'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

        # 获取或创建 token
        token, _ = Token.objects.get_or_create(user=user)

        return Response({
            'token': token.key,
            'user': UserSerializer(user).data
        })


class LogoutView(APIView):
    """登出"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.user.auth_token.delete()
        return Response({'message': '已登出'})


class MeView(APIView):
    """获取当前用户信息"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)
