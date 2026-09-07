"""Shared student-facing publication scopes for AI problems."""

from django.db.models import Q
from django.shortcuts import get_object_or_404

from users.grade_levels import normalize_grade, normalize_student_identifier

from .models import AUDIENCE_ALL_SCHOOL, AUDIENCE_CLASS, AUDIENCE_GRADE_ALL, Problem


def visible_problems_for_student(queryset, user):
    if not user or not user.is_authenticated or not user.is_active or user.role != 'student':
        return queryset.none()
    try:
        grade = normalize_grade(user.grade)
        class_num = normalize_student_identifier(user.class_num, label='班级')
    except Exception:
        return queryset.none()

    audience_match = (
        Q(audience_rules__is_active=True, audience_rules__scope_type=AUDIENCE_ALL_SCHOOL)
        | Q(
            audience_rules__is_active=True,
            audience_rules__scope_type=AUDIENCE_GRADE_ALL,
            audience_rules__grade=grade,
        )
        | Q(
            audience_rules__is_active=True,
            audience_rules__scope_type=AUDIENCE_CLASS,
            audience_rules__grade=grade,
            audience_rules__class_num=class_num,
        )
    )
    return queryset.filter(
        archived_at__isnull=True,
        publishing_suspended=False,
    ).filter(audience_match).distinct()


def student_can_access_problem(user, problem):
    return visible_problems_for_student(
        Problem.objects.filter(pk=problem.pk), user,
    ).exists()


def get_visible_problem_or_404(user, problem_id, *, course='ai'):
    queryset = visible_problems_for_student(
        Problem.objects.filter(course=course), user,
    )
    return get_object_or_404(queryset, problem_id=problem_id)
