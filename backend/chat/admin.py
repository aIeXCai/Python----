from django.contrib import admin
from .models import ChatSession, ChatMessage


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'title', 'context_type', 'context_id', 'created_at', 'updated_at']
    list_filter = ['context_type', 'created_at']
    search_fields = ['title', 'user__display_name', 'user__username']


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'session', 'role', 'content_preview', 'created_at']
    list_filter = ['role', 'created_at']
    search_fields = ['content']

    def content_preview(self, obj):
        return obj.content[:80]
    content_preview.short_description = '内容预览'
