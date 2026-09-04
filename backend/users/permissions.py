from rest_framework.permissions import BasePermission

from .scopes import is_platform_admin


class IsTeacher(BasePermission):
    message = '当前账号没有教师管理权限。'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
            and (request.user.role == 'teacher' or is_platform_admin(request.user))
        )


class IsStudent(BasePermission):
    message = '当前账号没有学生代码执行权限。'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
            and request.user.role == 'student'
        )
