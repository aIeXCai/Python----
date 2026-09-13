from django.contrib import admin
from .models import (
    AIChoiceQuestion, AIQuizAttempt, AIQuizAudience, AIQuizManagementAudit,
    AIQuizProgrammingItem, AIQuizSession, AIUnit, Problem, ProblemAudience,
    ProblemManagementAudit, Submission,
)


@admin.register(AIUnit)
class AIUnitAdmin(admin.ModelAdmin):
    list_display = [
        'display_name', 'name', 'grade', 'parent', 'order', 'archived_at',
        'created_by', 'updated_at',
    ]
    list_filter = ['grade', 'archived_at']
    search_fields = ['name', 'display_name']
    ordering = ['grade', 'order', 'id']
    readonly_fields = ['created_by', 'archived_at', 'created_at', 'updated_at']


@admin.register(AIChoiceQuestion)
class AIChoiceQuestionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'short_text', 'unit', 'difficulty', 'management_version',
        'archived_at', 'created_by', 'updated_at',
    ]
    list_filter = ['difficulty', 'unit__grade', 'archived_at']
    search_fields = ['text', 'category', 'unit__name', 'unit__display_name']
    readonly_fields = [
        'created_by', 'management_version', 'archived_at', 'created_at', 'updated_at',
    ]
    list_select_related = ['unit', 'unit__parent', 'created_by']

    @admin.display(description='题干')
    def short_text(self, obj):
        return obj.text[:50]


class AIQuizProgrammingItemInline(admin.TabularInline):
    model = AIQuizProgrammingItem
    extra = 0
    readonly_fields = ['problem', 'position', 'points']
    can_delete = False


class AIQuizAudienceInline(admin.TabularInline):
    model = AIQuizAudience
    extra = 0
    readonly_fields = [
        'scope_type', 'grade', 'class_num', 'is_active', 'configured_by',
        'created_at', 'updated_at',
    ]
    can_delete = False


@admin.register(AIQuizSession)
class AIQuizSessionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'title', 'content_grade', 'status', 'management_version',
        'blueprint_version', 'created_by', 'archived_at', 'updated_at',
    ]
    list_filter = ['content_grade', 'status', 'archived_at']
    search_fields = ['title']
    readonly_fields = [
        'created_by', 'management_version', 'blueprint_version', 'blueprint_json',
        'blueprint_hash', 'opened_at', 'closed_at', 'archived_at',
        'created_at', 'updated_at',
    ]
    inlines = [AIQuizProgrammingItemInline, AIQuizAudienceInline]


@admin.register(AIQuizManagementAudit)
class AIQuizManagementAuditAdmin(admin.ModelAdmin):
    list_display = [
        'event_type', 'outcome', 'actor_user_id', 'object_type',
        'object_id', 'reason_code', 'created_at',
    ]
    list_filter = ['event_type', 'outcome', 'created_at']
    search_fields = ['actor_user_id', 'object_id', 'reason_code']
    readonly_fields = [
        'event_type', 'outcome', 'actor_user_id', 'object_type', 'object_id',
        'reason_code', 'before_summary', 'after_summary', 'source_ip', 'created_at',
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AIQuizAttempt)
class AIQuizAttemptAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'session', 'attempt_no', 'status', 'answer_revision',
        'grade', 'class_num', 'started_at', 'deadline_at', 'settled_at',
    ]
    list_filter = ['status', 'grade', 'session']
    search_fields = ['user__username', 'student_number', 'session__title']
    readonly_fields = [field.name for field in AIQuizAttempt._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ProblemAudienceInline(admin.TabularInline):
    model = ProblemAudience
    extra = 0


@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display = [
        'problem_id', 'title', 'unit', 'grade_tag', 'difficulty', 'publishing_suspended',
        'archived_at', 'management_version', 'created_at',
    ]
    list_filter = ['course', 'unit__grade', 'grade_tag', 'publishing_suspended', 'archived_at']
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
