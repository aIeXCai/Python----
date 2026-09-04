import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .constants import (
    RUNNER_STATUS_CHOICES,
    RUNNER_STATUS_OFFLINE,
    STATUS_CHOICES,
    STATUS_QUEUED,
    TASK_TYPE_CHOICES,
)


class ExecutionTask(models.Model):
    """Durable queue record for one untrusted code execution request."""

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='execution_tasks',
    )
    problem = models.ForeignKey(
        'ai_courses.Problem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='execution_tasks',
    )
    task_type = models.CharField(max_length=16, choices=TASK_TYPE_CHOICES)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=STATUS_QUEUED, db_index=True)
    code = models.TextField()
    stdin = models.TextField(blank=True)
    test_snapshot = models.JSONField(null=True, blank=True)
    snapshot_hash = models.CharField(max_length=64)
    limits = models.JSONField(default=dict)
    idempotency_key = models.CharField(max_length=128)
    priority = models.PositiveSmallIntegerField(default=100)
    queued_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    leased_by = models.CharField(max_length=100, blank=True)
    lease_token_hash = models.CharField(max_length=64, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    stdout = models.TextField(blank=True)
    stderr = models.TextField(blank=True)
    result_detail = models.JSONField(default=dict, blank=True)
    score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    execution_ms = models.PositiveIntegerField(null=True, blank=True)
    queue_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = (
            models.UniqueConstraint(
                fields=('user', 'idempotency_key'),
                name='execution_unique_user_idempotency',
            ),
            models.CheckConstraint(
                condition=models.Q(score__isnull=True) | models.Q(score__gte=0, score__lte=100),
                name='execution_score_valid_range',
            ),
        )
        indexes = (
            models.Index(fields=('status', 'priority', 'queued_at'), name='exec_queue_idx'),
            models.Index(fields=('user', 'status', 'created_at'), name='exec_user_status_idx'),
            models.Index(fields=('lease_expires_at', 'status'), name='exec_lease_idx'),
        )

    def __str__(self):
        return f'{self.public_id} ({self.task_type}/{self.status})'


class RunnerNode(models.Model):
    """Last-known health metadata for a trusted Runner controller."""

    runner_id = models.CharField(max_length=100, primary_key=True)
    protocol_version = models.CharField(max_length=32)
    sandbox_image_digest = models.CharField(max_length=200)
    capacity = models.PositiveSmallIntegerField(default=1)
    active_slots = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(
        max_length=16,
        choices=RUNNER_STATUS_CHOICES,
        default=RUNNER_STATUS_OFFLINE,
        db_index=True,
    )
    last_heartbeat_at = models.DateTimeField()
    last_error = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('runner_id',)

    def __str__(self):
        return self.runner_id


class RunnerRequestReceipt(models.Model):
    """Persistent replay guard for signed Runner requests."""

    runner_id = models.CharField(max_length=100)
    request_id = models.UUIDField()
    endpoint = models.CharField(max_length=200)
    request_hash = models.CharField(max_length=64)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=('runner_id', 'request_id'),
                name='runner_request_unique_id',
            ),
        )
        indexes = (
            models.Index(fields=('created_at',), name='runner_receipt_created_idx'),
        )
