import uuid

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('ai_courses', '0003_problem_template_code'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RunnerNode',
            fields=[
                ('runner_id', models.CharField(max_length=100, primary_key=True, serialize=False)),
                ('protocol_version', models.CharField(max_length=32)),
                ('sandbox_image_digest', models.CharField(max_length=200)),
                ('capacity', models.PositiveSmallIntegerField(default=1)),
                ('active_slots', models.PositiveSmallIntegerField(default=0)),
                ('status', models.CharField(choices=[('online', '在线'), ('draining', '停止领取'), ('offline', '离线')], db_index=True, default='offline', max_length=16)),
                ('last_heartbeat_at', models.DateTimeField()),
                ('last_error', models.CharField(blank=True, max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ('runner_id',)},
        ),
        migrations.CreateModel(
            name='ExecutionTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('task_type', models.CharField(choices=[('run', '自由运行'), ('grade', '自动评测')], max_length=16)),
                ('status', models.CharField(choices=[('queued', '排队中'), ('running', '运行中'), ('succeeded', '成功'), ('runtime_error', '运行错误'), ('wrong_answer', '答案错误'), ('timed_out', '超时'), ('resource_limited', '资源超限'), ('system_error', '系统错误'), ('cancelled', '已取消')], db_index=True, default='queued', max_length=24)),
                ('code', models.TextField()),
                ('stdin', models.TextField(blank=True)),
                ('test_snapshot', models.JSONField(blank=True, null=True)),
                ('snapshot_hash', models.CharField(max_length=64)),
                ('limits', models.JSONField(default=dict)),
                ('idempotency_key', models.CharField(max_length=128)),
                ('priority', models.PositiveSmallIntegerField(default=100)),
                ('queued_at', models.DateTimeField(auto_now_add=True)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField()),
                ('leased_by', models.CharField(blank=True, max_length=100)),
                ('lease_token_hash', models.CharField(blank=True, max_length=64)),
                ('lease_expires_at', models.DateTimeField(blank=True, null=True)),
                ('attempt_count', models.PositiveSmallIntegerField(default=0)),
                ('stdout', models.TextField(blank=True)),
                ('stderr', models.TextField(blank=True)),
                ('result_detail', models.JSONField(blank=True, default=dict)),
                ('score', models.FloatField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ('execution_ms', models.PositiveIntegerField(blank=True, null=True)),
                ('queue_ms', models.PositiveIntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('problem', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='execution_tasks', to='ai_courses.problem')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='execution_tasks', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-created_at',),
                'indexes': [models.Index(fields=['status', 'priority', 'queued_at'], name='exec_queue_idx'), models.Index(fields=['user', 'status', 'created_at'], name='exec_user_status_idx'), models.Index(fields=['lease_expires_at', 'status'], name='exec_lease_idx')],
                'constraints': [models.UniqueConstraint(fields=('user', 'idempotency_key'), name='execution_unique_user_idempotency'), models.CheckConstraint(condition=models.Q(('score__isnull', True), models.Q(('score__gte', 0), ('score__lte', 100)), _connector='OR'), name='execution_score_valid_range')],
            },
        ),
    ]
