from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

from .grade_levels import (
    GRADE_CHOICES as CANONICAL_GRADE_CHOICES,
    normalize_grade,
    normalize_student_identifier,
)


class CustomUser(AbstractUser):
    """扩展 Django 默认 User 模型"""

    ROLE_CHOICES = [
        ('student', '学生'),
        ('teacher', '老师'),
    ]

    GRADE_CHOICES = CANONICAL_GRADE_CHOICES

    role = models.CharField(
        '角色', max_length=20, choices=ROLE_CHOICES, default='student'
    )
    grade = models.CharField(
        '年级', max_length=10, choices=GRADE_CHOICES, blank=True, null=True
    )
    class_num = models.CharField(
        '班级', max_length=20, blank=True, null=True
    )
    student_number = models.CharField(
        '班级内学号', max_length=20, blank=True, null=True
    )
    # 学生真实姓名（登录时不验证，仅用于显示）
    display_name = models.CharField('显示姓名', max_length=100, blank=True, null=True)
    PASSWORD_RECOVERY_CHOICES = [
        ('available', '可安全查看'),
        ('missing_legacy', '历史密码缺失'),
        ('hash_mismatch', '历史密码与哈希不一致'),
        ('not_applicable', '不适用'),
    ]
    encrypted_password = models.TextField(
        '学生密码密文', blank=True, null=True, editable=False
    )
    password_encryption_key_id = models.CharField(
        '学生密码密钥版本', max_length=40, blank=True, null=True, editable=False
    )
    password_recovery_status = models.CharField(
        '密码恢复状态',
        max_length=32,
        choices=PASSWORD_RECOVERY_CHOICES,
        default='not_applicable',
        editable=False,
    )
    # 老师的管理范围（信息科技课用）
    managed_grade = models.CharField(
        '管理年级', max_length=10, choices=GRADE_CHOICES, blank=True, null=True
    )

    class Meta:
        verbose_name = '用户'
        verbose_name_plural = '用户'
        constraints = [
            models.UniqueConstraint(
                fields=['grade', 'class_num', 'student_number'],
                name='users_unique_student_identity',
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(role='student')
                    | models.Q(is_superuser=True)
                    | (
                        models.Q(grade__isnull=False)
                        & ~models.Q(grade='')
                        & models.Q(class_num__isnull=False)
                        & ~models.Q(class_num='')
                        & models.Q(student_number__isnull=False)
                        & ~models.Q(student_number='')
                    )
                ),
                name='users_student_identity_required',
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(role='teacher')
                    | (
                        models.Q(grade__isnull=True)
                        & models.Q(class_num__isnull=True)
                        & models.Q(student_number__isnull=True)
                    )
                ),
                name='users_teacher_identity_is_null',
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(password_recovery_status='available')
                    | (
                        models.Q(role='student')
                        & models.Q(encrypted_password__isnull=False)
                        & ~models.Q(encrypted_password='')
                        & models.Q(password_encryption_key_id__isnull=False)
                        & ~models.Q(password_encryption_key_id='')
                    )
                ),
                name='users_available_password_has_ciphertext',
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.role == 'student':
            try:
                self.grade = normalize_grade(self.grade)
            except ValidationError as exc:
                errors['grade'] = exc.messages
            for field, label in (
                ('class_num', '班级'),
                ('student_number', '班内学号'),
            ):
                try:
                    setattr(
                        self,
                        field,
                        normalize_student_identifier(
                            getattr(self, field), label=label,
                            max_length=self._meta.get_field(field).max_length,
                        ),
                    )
                except ValidationError as exc:
                    errors[field] = exc.messages
        elif self.role == 'teacher':
            self.grade = None
            self.class_num = None
            self.student_number = None
            try:
                self.managed_grade = normalize_grade(
                    self.managed_grade, allow_blank=True,
                )
            except ValidationError as exc:
                errors['managed_grade'] = exc.messages
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        if self.grade and self.class_num:
            return f"{self.username} ({self.grade}{self.class_num})"
        return self.username


class PasswordSecurityAudit(models.Model):
    EVENT_CHOICES = [
        ('reveal', '查看学生密码'),
        ('manual_reset', '手工重置密码'),
        ('generated_reset', '生成临时密码'),
    ]
    OUTCOME_CHOICES = [
        ('success', '成功'),
        ('denied', '拒绝'),
        ('not_found', '目标不存在'),
        ('unavailable', '密码不可恢复'),
        ('rate_limited', '触发限流'),
        ('error', '安全失败'),
    ]

    event_type = models.CharField(max_length=24, choices=EVENT_CHOICES)
    actor_user_id = models.PositiveBigIntegerField(blank=True, null=True)
    target_user_id = models.PositiveBigIntegerField(blank=True, null=True)
    outcome = models.CharField(max_length=24, choices=OUTCOME_CHOICES)
    reason_code = models.CharField(max_length=48, blank=True)
    source_ip = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '密码安全审计'
        verbose_name_plural = '密码安全审计'
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['actor_user_id', 'event_type', 'created_at'],
                name='pwd_audit_actor_event_time',
            ),
            models.Index(
                fields=['target_user_id', 'created_at'],
                name='pwd_audit_target_time',
            ),
            models.Index(
                fields=['outcome', 'created_at'],
                name='pwd_audit_outcome_time',
            ),
        ]

    def __str__(self):
        return f'{self.event_type}:{self.outcome}@{self.created_at:%Y-%m-%d %H:%M:%S}'
