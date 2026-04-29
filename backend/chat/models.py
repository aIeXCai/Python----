from django.db import models
from django.conf import settings


class ChatSession(models.Model):
    """AI 对话会话"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_sessions',
    )
    title = models.CharField(max_length=200, default='新对话')
    context_type = models.CharField(max_length=50, null=True, blank=True)
    context_id = models.CharField(max_length=100, null=True, blank=True)
    context_snapshot = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.title} (#{self.id})'


class ChatMessage(models.Model):
    """对话消息"""
    ROLE_CHOICES = [
        ('user', '用户'),
        ('assistant', 'AI'),
    ]

    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'[{self.role}] {self.content[:50]}'
