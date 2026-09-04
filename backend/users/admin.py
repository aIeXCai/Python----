from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin
from django.http import HttpResponseRedirect
from django.urls import reverse
from .models import CustomUser, PasswordSecurityAudit


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

    def user_change_password(self, request, user_id, form_url=''):
        user = self.get_object(request, user_id)
        if user is not None and user.role == 'student':
            messages.error(request, '学生密码请在教师端学生管理页面重置。')
            return HttpResponseRedirect(
                reverse('admin:users_customuser_change', args=(user_id,))
            )
        return super().user_change_password(request, user_id, form_url)


@admin.register(PasswordSecurityAudit)
class PasswordSecurityAuditAdmin(admin.ModelAdmin):
    list_display = [
        'event_type', 'outcome', 'actor_user_id', 'target_user_id',
        'reason_code', 'source_ip', 'created_at',
    ]
    list_filter = ['event_type', 'outcome', 'created_at']
    search_fields = ['actor_user_id', 'target_user_id', 'reason_code']
    readonly_fields = [
        'event_type', 'outcome', 'actor_user_id', 'target_user_id',
        'reason_code', 'source_ip', 'created_at',
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
