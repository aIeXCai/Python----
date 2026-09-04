from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from .grade_levels import normalize_grade, normalize_student_identifier
from .models import CustomUser
from .scopes import (
    TeacherScopeError,
    require_teacher_grade,
    scope_students,
)


class GradeNormalizationTest(TestCase):
    def test_canonical_and_alias_grades(self):
        self.assertEqual(normalize_grade(' 七年级 '), '七年级')
        self.assertEqual(normalize_grade('初一'), '七年级')
        self.assertEqual(normalize_grade('初二'), '八年级')
        self.assertEqual(normalize_grade('初三'), '九年级')

    def test_unknown_grade_is_rejected(self):
        with self.assertRaises(ValidationError):
            normalize_grade('六年级')

    def test_identifier_preserves_leading_zero_and_rejects_controls(self):
        self.assertEqual(normalize_student_identifier(' 01 '), '01')
        with self.assertRaises(ValidationError):
            normalize_student_identifier('1\n2')


class TeacherScopeTest(TestCase):
    def setUp(self):
        self.grade7 = CustomUser.objects.create_user(
            username='grade7', password='x', role='student', grade='七年级',
            class_num='1', student_number='01',
        )
        self.grade8 = CustomUser.objects.create_user(
            username='grade8', password='x', role='student', grade='八年级',
            class_num='1', student_number='01',
        )
        self.teacher = CustomUser.objects.create_user(
            username='teacher7', password='x', role='teacher', managed_grade='七年级',
        )

    def test_teacher_scope_only_contains_managed_grade(self):
        scoped = scope_students(CustomUser.objects.filter(role='student'), self.teacher)
        self.assertEqual(list(scoped), [self.grade7])

    def test_missing_scope_is_fail_closed(self):
        teacher = CustomUser.objects.create_user(username='no-scope', password='x', role='teacher')
        self.assertFalse(scope_students(CustomUser.objects.all(), teacher).exists())
        with self.assertRaises(TeacherScopeError) as caught:
            require_teacher_grade(teacher)
        self.assertEqual(caught.exception.code, 'teacher_scope_missing')

    def test_cross_grade_is_rejected_and_superuser_can_cross(self):
        with self.assertRaises(TeacherScopeError):
            require_teacher_grade(self.teacher, '八年级')
        admin = CustomUser.objects.create_superuser(
            username='root', password='x', role='teacher',
        )
        self.assertEqual(require_teacher_grade(admin, '初二'), '八年级')


class StudentIdentityConstraintTest(TestCase):
    def test_database_rejects_duplicate_grade_class_and_number(self):
        CustomUser.objects.create_user(
            username='identity-one', password='x', role='student',
            grade='七年级', class_num='1', student_number='01',
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            CustomUser.objects.create_user(
                username='identity-two', password='x', role='student',
                grade='七年级', class_num='1', student_number='01',
            )
