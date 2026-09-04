from rest_framework.permissions import BasePermission


class IsStudent(BasePermission):
    message = '当前账号没有学生作答权限。'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == 'student'
        )
