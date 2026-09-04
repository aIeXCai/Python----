"""Server-side data scopes for teachers and platform administrators."""

from dataclasses import dataclass

from .grade_levels import normalize_grade


@dataclass
class TeacherScopeError(Exception):
    code: str
    message: str

    def __str__(self):
        return self.message


def is_platform_admin(user):
    return bool(user and user.is_authenticated and user.is_active and user.is_superuser)


def teacher_grade(user):
    if is_platform_admin(user):
        return None
    if not user or not user.is_authenticated or not user.is_active or user.role != 'teacher':
        raise TeacherScopeError('teacher_role_required', '当前账号没有教师管理权限')
    try:
        return normalize_grade(user.managed_grade)
    except Exception as exc:
        raise TeacherScopeError(
            'teacher_scope_missing', '请先为教师账号设置管理年级',
        ) from exc


def scope_students(queryset, teacher):
    if is_platform_admin(teacher):
        return queryset
    try:
        grade = teacher_grade(teacher)
    except TeacherScopeError:
        return queryset.none()
    return queryset.filter(grade=grade)


def require_teacher_grade(teacher, requested_grade=None):
    if is_platform_admin(teacher):
        try:
            return normalize_grade(requested_grade, allow_blank=True)
        except Exception as exc:
            raise TeacherScopeError('invalid_grade', '年级不在允许范围内') from exc
    grade = teacher_grade(teacher)
    if requested_grade not in (None, ''):
        try:
            requested = normalize_grade(requested_grade)
        except Exception as exc:
            raise TeacherScopeError('invalid_grade', '年级不在允许范围内') from exc
        if requested != grade:
            raise TeacherScopeError(
                'teacher_grade_forbidden', '不能访问管理范围外的年级',
            )
    return grade


def scope_by_grade(queryset, teacher, field='grade'):
    if is_platform_admin(teacher):
        return queryset
    try:
        grade = teacher_grade(teacher)
    except TeacherScopeError:
        return queryset.none()
    return queryset.filter(**{field: grade})
