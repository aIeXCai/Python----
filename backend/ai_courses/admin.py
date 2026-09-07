from django.contrib import admin
from .models import Problem, ProblemAudience, ProblemManagementAudit, Submission


class ProblemAudienceInline(admin.TabularInline):
    model = ProblemAudience
    extra = 0


@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display = [
        'problem_id', 'title', 'grade_tag', 'difficulty', 'publishing_suspended',
        'archived_at', 'management_version', 'created_at',
    ]
    list_filter = ['course', 'grade_tag', 'publishing_suspended', 'archived_at']
    search_fields = ['problem_id', 'title']
    ordering = ['problem_id']
    inlines = [ProblemAudienceInline]


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ['user', 'problem', 'score', 'status', 'submitted_at']
    list_filter = ['status', 'problem', 'submitted_at']
    search_fields = ['user__username', 'problem__problem_id']
    ordering = ['-submitted_at']


@admin.register(ProblemManagementAudit)
class ProblemManagementAuditAdmin(admin.ModelAdmin):
    list_display = [
        'event_type', 'outcome', 'actor_user_id', 'problem_id',
        'reason_code', 'source_ip', 'created_at',
    ]
    list_filter = ['event_type', 'outcome', 'created_at']
    search_fields = ['actor_user_id', 'problem_id', 'reason_code']
    readonly_fields = [
        'event_type', 'outcome', 'actor_user_id', 'problem_id',
        'reason_code', 'before_summary', 'after_summary', 'source_ip', 'created_at',
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
