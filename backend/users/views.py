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

        username = serializer.validated_data.get('username')
        password = serializer.validated_data['password']
        grade = serializer.validated_data.get('grade')
        class_num = serializer.validated_data.get('class_num')
        student_number = serializer.validated_data.get('student_number')

        user = None

        # 优先：学生用 grade+class_num+student_number 登录
        if grade and class_num and student_number:
            try:
                user = CustomUser.objects.get(
                    grade=grade,
                    class_num=class_num,
                    student_number=student_number,
                    role='student'
                )
                if not user.check_password(password):
                    return Response(
                        {'error': '密码错误'},
                        status=status.HTTP_401_UNAUTHORIZED
                    )
            except CustomUser.DoesNotExist:
                return Response(
                    {'error': '学生信息不存在'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
        else:
            # 老师用 username + password 登录
            if not username:
                return Response(
                    {'error': '请提供用户名'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            user = authenticate(username=username, password=password)
            if not user:
                return Response(
                    {'error': '用户名或密码错误'},
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


class RegisterView(APIView):
    """学生注册"""
    permission_classes = [AllowAny]

    # 年级代码映射（用于生成 username）
    GRADE_CODE = {
        '初一': '7', '初二': '8', '初三': '9',
        '高一': '10', '高二': '11', '高三': '12',
    }

    def post(self, request):
        grade = request.data.get('grade')
        class_num = request.data.get('class_num')
        student_number = request.data.get('student_number')
        display_name = request.data.get('display_name') or request.data.get('name')
        password = request.data.get('password')

        # 基础验证
        if not all([grade, class_num, student_number, password]):
            return Response({'error': '缺少必要参数'}, status=status.HTTP_400_BAD_REQUEST)

        if not display_name:
            return Response({'error': '请填写姓名'}, status=status.HTTP_400_BAD_REQUEST)

        # 检查年级+班级+学号是否已存在
        if CustomUser.objects.filter(grade=grade, class_num=class_num, student_number=student_number, role='student').exists():
            return Response({'error': '该学生已存在，请直接登录'}, status=status.HTTP_400_BAD_REQUEST)

        # 生成 username：年级代码-班级-学号（如 8-3-01）
        grade_code = self.GRADE_CODE.get(grade, grade)
        username = f"{grade_code}-{class_num}-{student_number}"

        # 如果 username 冲突，加随机后缀
        if CustomUser.objects.filter(username=username).exists():
            import uuid
            username = f"{username}-{uuid.uuid4().hex[:4]}"

        # 创建用户
        user = CustomUser.objects.create(
            username=username,
            role='student',
            grade=grade,
            class_num=class_num,
            student_number=str(student_number),
            display_name=display_name,
            plain_password=password,
        )
        user.set_password(password)
        user.save()

        # 自动登录，发 token
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)


class UserDetailView(APIView):
    """老师查看/编辑/删除单个学生"""
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        """获取学生详情（含明文密码，供老师查看）"""
        if request.user.role != 'teacher':
            return Response({'error': '权限不足'}, status=status.HTTP_403_FORBIDDEN)
        try:
            user = CustomUser.objects.get(id=user_id, role='student')
        except CustomUser.DoesNotExist:
            return Response({'error': '学生不存在'}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'id': user.id,
            'username': user.username,
            'display_name': user.display_name,
            'grade': user.grade,
            'class_num': user.class_num,
            'student_number': user.student_number,
            'plain_password': user.plain_password or '',
            'role': user.role,
        })

    def put(self, request, user_id):
        """编辑学生信息"""
        if request.user.role != 'teacher':
            return Response({'error': '权限不足'}, status=status.HTTP_403_FORBIDDEN)
        try:
            user = CustomUser.objects.get(id=user_id, role='student')
        except CustomUser.DoesNotExist:
            return Response({'error': '学生不存在'}, status=status.HTTP_404_NOT_FOUND)

        grade = request.data.get('grade')
        class_num = request.data.get('class_num')
        student_number = request.data.get('student_number')
        display_name = request.data.get('display_name')
        password = request.data.get('password')

        if grade: user.grade = grade
        if class_num: user.class_num = class_num
        if student_number: user.student_number = str(student_number)
        if display_name: user.display_name = display_name
        if password:
            user.set_password(password)
            user.plain_password = password

        user.save()
        return Response({'student': UserSerializer(user).data})

    def delete(self, request, user_id):
        """删除学生"""
        if request.user.role != 'teacher':
            return Response({'error': '权限不足'}, status=status.HTTP_403_FORBIDDEN)
        try:
            user = CustomUser.objects.get(id=user_id, role='student')
        except CustomUser.DoesNotExist:
            return Response({'error': '学生不存在'}, status=status.HTTP_404_NOT_FOUND)
        user.delete()
        return Response({'message': '已删除'}, status=status.HTTP_204_NO_CONTENT)

