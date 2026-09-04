from django.contrib import admin

from .models import ExecutionTask, RunnerNode


class ReadOnlyRuntimeAdmin(admin.ModelAdmin):
    """Runtime state must only be changed through the execution services."""

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ExecutionTask)
class ExecutionTaskAdmin(ReadOnlyRuntimeAdmin):
    list_display = ('public_id', 'user', 'task_type', 'status', 'problem', 'queued_at', 'finished_at')
    list_filter = ('task_type', 'status')
    search_fields = ('public_id', 'user__username', 'problem__problem_id')


@admin.register(RunnerNode)
class RunnerNodeAdmin(ReadOnlyRuntimeAdmin):
    list_display = ('runner_id', 'status', 'active_slots', 'capacity', 'last_heartbeat_at')
    list_filter = ('status', 'protocol_version')
    search_fields = ('runner_id', 'sandbox_image_digest')
