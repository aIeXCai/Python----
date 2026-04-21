from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'role', 'grade', 'class_num', 'student_number', 'is_staff']
    list_filter = ['role', 'grade']
    search_fields = ['username', 'grade', 'class_num']

    fieldsets = UserAdmin.fieldsets + (
        ('扩展信息', {'fields': ('role', 'grade', 'class_num', 'student_number', 'managed_grade')}),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ('扩展信息', {'fields': ('role', 'grade', 'class_num', 'student_number', 'managed_grade')}),
    )
