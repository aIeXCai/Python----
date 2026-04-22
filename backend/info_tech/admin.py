from django.contrib import admin
from .models import Unit, Question, QuizSession, QuizSubmission


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_name', 'order']
    ordering = ['order']


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['id', 'unit', 'difficulty', 'category', 'text', 'answer', 'created_at']
    list_filter = ['unit', 'difficulty', 'category']
    search_fields = ['text']
    ordering = ['id']


@admin.register(QuizSession)
class QuizSessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'created_by', 'num_questions', 'is_visible', 'created_at']
    list_filter = ['is_visible', 'created_at']
    filter_horizontal = ['units']
    ordering = ['-created_at']


@admin.register(QuizSubmission)
class QuizSubmissionAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'session', 'score', 'correct_count', 'total_count', 'submitted_at']
    list_filter = ['session', 'submitted_at']
    ordering = ['-submitted_at']
