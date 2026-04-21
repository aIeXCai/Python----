from django.contrib import admin
from .models import Problem, Submission


@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display = ['problem_id', 'title', 'difficulty', 'created_at']
    search_fields = ['problem_id', 'title']
    ordering = ['problem_id']


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ['user', 'problem', 'score', 'status', 'submitted_at']
    list_filter = ['status', 'problem', 'submitted_at']
    search_fields = ['user__username', 'problem__problem_id']
    ordering = ['-submitted_at']
