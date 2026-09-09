import uuid

from django.conf import settings
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import ExpiringTokenAuthentication, get_or_create_valid_token
from .models import CustomUser
from .grade_levels import normalize_grade, normalize_student_identifier
from .permissions import IsTeacher
from .scopes import TeacherScopeError, require_teacher_grade, scope_students
from .serializers import LoginSerializer, PasswordResetSerializer, UserSerializer
from .services import (
    PasswordRevealRateLimited,
    StudentPasswordUnavailable,
    StudentTargetNotFound,
    TeacherAuthorizationChanged,
    record_password_audit,
    reset_student_password,
    reveal_student_password,
    safe_source_ip,
    set_student_password,
)


def no_store_response(data, *, status_code=status.HTTP_200_OK):
    response = Response(data, status=status_code)
    response['Cache-Control'] = 'no-store, private, max-age=0'
    response['Pragma'] = 'no-cache'
    return response


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': '参数错误', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        values = serializer.validated_data
        password = values['password']
        grade = values.get('grade')
        class_num = values.get('class_num')
        student_number = values.get('student_number')
        if grade and class_num and student_number:
            try:
                user = CustomUser.objects.get(
                    grade=grade,
                    class_num=class_num,
                    student_number=student_number,
                    role='student',
                )
            except CustomUser.DoesNotExist:
                return Response(
                    {'error': '学生信息不存在'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            if not user.is_active or not user.check_password(password):
                return Response(
                    {'error': '密码错误'}, status=status.HTTP_401_UNAUTHORIZED
                )
        else:
            username = values.get('username')
            if not username:
                return Response(
                    {'error': '请提供用户名'}, status=status.HTTP_400_BAD_REQUEST
                )
            user = authenticate(username=username, password=password)
            if not user:
                return Response(
                    {'error': '用户名或密码错误'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

        token = get_or_create_valid_token(user)
        return Response({'token': token.key, 'user': UserSerializer(user).data})


class LogoutView(APIView):
    authentication_classes = [ExpiringTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.auth.delete()
        return Response({'message': '已登出'})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class RegisterView(APIView):
    permission_classes = [AllowAny]
    GRADE_CODE = {
        '七年级': '7', '八年级': '8', '九年级': '9',
        '高一': '10', '高二': '11', '高三': '12',
    }

    def post(self, request):
        try:
            grade = normalize_grade(request.data.get('grade'))
            class_num = normalize_student_identifier(
                request.data.get('class_num'), label='班级',
            )
            student_number = normalize_student_identifier(
                request.data.get('student_number'), label='班内学号',
            )
        except ValidationError as exc:
            return Response(
                {'error': '学生身份信息无效', 'details': exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )
        display_name = request.data.get('display_name') or request.data.get('name')
        password = request.data.get('password')
        if not password:
            return Response(
                {'error': '缺少必要参数'}, status=status.HTTP_400_BAD_REQUEST
            )
        if not display_name:
            return Response(
                {'error': '请填写姓名'}, status=status.HTTP_400_BAD_REQUEST
            )
        if CustomUser.objects.filter(
            grade=grade,
            class_num=class_num,
            student_number=student_number,
            role='student',
        ).exists():
            return Response(
                {'error': '该学生已存在，请直接登录'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        grade_code = self.GRADE_CODE[grade]
        username = f'{grade_code}-{class_num}-{student_number}'
        if CustomUser.objects.filter(username=username).exists():
            username = f'{username}-{uuid.uuid4().hex[:4]}'
        user = CustomUser(
            username=username,
            role='student',
            grade=grade,
            class_num=class_num,
            student_number=str(student_number),
            display_name=display_name,
        )
        try:
            with transaction.atomic():
                # 学生自主注册：不强制密码强度/长度下限（课堂场景便于记忆）
                # 教师端重置/设置学生密码仍走强校验（set_student_password 默认 validate=True）
                set_student_password(
                    user, password, validate=False, invalidate_tokens=False
                )
                token = get_or_create_valid_token(user)
        except IntegrityError:
            return Response(
                {'error': '该学生已存在，请直接登录'},
                status=status.HTTP_409_CONFLICT,
            )
        except ValidationError as exc:
            return Response(
                {'error': '密码不符合安全要求', 'details': exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {'token': token.key, 'user': UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


class UserDetailView(APIView):
    permission_classes = [IsTeacher]

    def get_object(self, teacher, user_id):
        return scope_students(
            CustomUser.objects.filter(role='student'), teacher,
        ).filter(id=user_id).first()

    def get(self, request, user_id):
        user = self.get_object(request.user, user_id)
        if user is None:
            return Response(
                {'error': '学生不存在'}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(UserSerializer(user).data)

    def put(self, request, user_id):
        if 'password' in request.data:
            return Response(
                {'error': '请使用专用密码重置接口'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = self.get_object(request.user, user_id)
        if user is None:
            return Response(
                {'error': '学生不存在'}, status=status.HTTP_404_NOT_FOUND
            )
        try:
            if 'grade' in request.data:
                user.grade = normalize_grade(request.data.get('grade'))
                require_teacher_grade(request.user, user.grade)
            if 'class_num' in request.data:
                user.class_num = normalize_student_identifier(
                    request.data.get('class_num'), label='班级',
                )
            if 'student_number' in request.data:
                user.student_number = normalize_student_identifier(
                    request.data.get('student_number'), label='班内学号',
                )
            if 'display_name' in request.data:
                user.display_name = str(request.data.get('display_name') or '').strip()
            user.full_clean()
            user.save()
        except TeacherScopeError as exc:
            return Response(
                {'error': exc.message, 'code': exc.code},
                status=status.HTTP_403_FORBIDDEN,
            )
        except ValidationError as exc:
            return Response(
                {'error': '学生信息无效', 'details': exc.message_dict},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except IntegrityError:
            return Response(
                {'error': '该年级、班级和学号已被使用'},
                status=status.HTTP_409_CONFLICT,
            )
        return Response({'student': UserSerializer(user).data})

    def delete(self, request, user_id):
        user = self.get_object(request.user, user_id)
        if user is None:
            return Response(
                {'error': '学生不存在'}, status=status.HTTP_404_NOT_FOUND
            )
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordSecurityAPIView(APIView):
    authentication_classes = [ExpiringTokenAuthentication]
    permission_classes = [IsTeacher]
    audit_event_type = 'reveal'

    def get_audit_event_type(self, request):
        return self.audit_event_type

    def permission_denied(self, request, message=None, code=None):
        actor = request.user if getattr(request.user, 'is_authenticated', False) else None
        record_password_audit(
            event_type=self.get_audit_event_type(request),
            outcome='denied',
            reason_code='not_teacher' if actor else 'anonymous',
            actor_user_id=actor.pk if actor else None,
            target_user_id=self.kwargs.get('user_id'),
            source_ip=safe_source_ip(request),
        )
        return super().permission_denied(request, message=message, code=code)


class PasswordRevealView(PasswordSecurityAPIView):
    audit_event_type = 'reveal'

    def post(self, request, user_id):
        try:
            plaintext = reveal_student_password(
                teacher=request.user,
                student_id=user_id,
                source_ip=safe_source_ip(request),
            )
        except StudentTargetNotFound:
            return no_store_response(
                {'error': '学生不存在'}, status_code=status.HTTP_404_NOT_FOUND
            )
        except StudentPasswordUnavailable:
            return no_store_response(
                {'error': '密码不可查看，请为学生重置密码'},
                status_code=status.HTTP_409_CONFLICT,
            )
        except PasswordRevealRateLimited:
            return no_store_response(
                {'error': '查看过于频繁，请稍后再试'},
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except TeacherAuthorizationChanged:
            return no_store_response(
                {'error': '当前账号没有教师管理权限'},
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return no_store_response(
            {'password': plaintext, 'display_seconds': settings.PASSWORD_REVEAL_SECONDS}
        )


class PasswordResetView(PasswordSecurityAPIView):
    audit_event_type = 'manual_reset'

    def get_audit_event_type(self, request):
        if isinstance(request.data, dict) and request.data.get('mode') == 'generated':
            return 'generated_reset'
        return 'manual_reset'

    def post(self, request, user_id):
        serializer = PasswordResetSerializer(data=request.data)
        if not serializer.is_valid():
            record_password_audit(
                event_type=self.get_audit_event_type(request), outcome='denied',
                reason_code='invalid_request', actor_user_id=request.user.pk,
                target_user_id=user_id, source_ip=safe_source_ip(request),
            )
            return no_store_response(
                {'error': '参数错误', 'details': serializer.errors},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        values = serializer.validated_data
        try:
            generated = reset_student_password(
                teacher=request.user,
                student_id=user_id,
                mode=values['mode'],
                plaintext=values.get('password'),
                source_ip=safe_source_ip(request),
            )
        except StudentTargetNotFound:
            return no_store_response(
                {'error': '学生不存在'}, status_code=status.HTTP_404_NOT_FOUND
            )
        except ValidationError as exc:
            return no_store_response(
                {'error': '新密码不符合安全要求', 'details': exc.messages},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except TeacherAuthorizationChanged:
            return no_store_response(
                {'error': '当前账号没有教师管理权限'},
                status_code=status.HTTP_403_FORBIDDEN,
            )
        if values['mode'] == 'generated':
            return no_store_response(
                {
                    'message': '临时密码已生成，学生原登录已失效',
                    'temporary_password': generated,
                    'display_seconds': settings.PASSWORD_REVEAL_SECONDS,
                }
            )
        return no_store_response({'message': '密码已重置，学生原登录已失效'})
