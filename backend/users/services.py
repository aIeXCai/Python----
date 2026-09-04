"""Transactional services for student password storage and controlled access."""

import ipaddress
import secrets
import string
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.authtoken.models import Token

from .models import CustomUser, PasswordSecurityAudit
from .security import PasswordEncryptionError, StudentPasswordCipher
from .scopes import is_platform_admin, teacher_grade


class StudentPasswordError(Exception):
    reason_code = 'security_error'


class StudentTargetNotFound(StudentPasswordError):
    reason_code = 'student_not_found'


class StudentPasswordUnavailable(StudentPasswordError):
    reason_code = 'password_unavailable'


class PasswordRevealRateLimited(StudentPasswordError):
    reason_code = 'rate_limited'


class TeacherAuthorizationChanged(StudentPasswordError):
    reason_code = 'teacher_role_changed'


def _authorized_student(teacher, student_id):
    student = CustomUser.objects.select_for_update().filter(
        pk=student_id, role='student',
    ).first()
    if student is None:
        return None, 'student_not_found'
    if is_platform_admin(teacher):
        return student, None
    try:
        managed_grade = teacher_grade(teacher)
    except Exception:
        return None, 'teacher_scope_missing'
    if student.grade != managed_grade:
        return None, 'teacher_grade_forbidden'
    return student, None


def safe_source_ip(request):
    value = request.META.get('REMOTE_ADDR') if request else None
    if not value:
        return None
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None


def record_password_audit(
    *, event_type, outcome, reason_code='', actor_user_id=None,
    target_user_id=None, source_ip=None,
):
    return PasswordSecurityAudit.objects.create(
        event_type=event_type,
        outcome=outcome,
        reason_code=reason_code,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        source_ip=source_ip,
    )


def set_student_password(
    student, plaintext, *, validate=True, invalidate_tokens=True
):
    if student.role != 'student':
        raise ValidationError('只能为学生账号设置可恢复密码。')
    if not isinstance(plaintext, str) or len(plaintext) > 128:
        raise ValidationError('密码长度必须在 8 到 128 位之间。')
    if validate:
        validate_password(plaintext, user=student)

    cipher = StudentPasswordCipher(settings.STUDENT_PASSWORD_KEY_CONFIG)
    ciphertext, key_id = cipher.encrypt(plaintext)
    with transaction.atomic():
        student.set_password(plaintext)
        student.encrypted_password = ciphertext
        student.password_encryption_key_id = key_id
        student.password_recovery_status = 'available'
        student.save()
        if invalidate_tokens and student.pk:
            Token.objects.filter(user=student).delete()
        recovered = cipher.decrypt(
            student.encrypted_password, student.password_encryption_key_id
        )
        if not student.check_password(recovered):
            raise RuntimeError('学生密码一致性校验失败。')
        del recovered
    return student


def reveal_student_password(*, teacher, student_id, source_ip=None):
    failure = None
    plaintext = None
    with transaction.atomic():
        locked_teacher = CustomUser.objects.select_for_update().get(pk=teacher.pk)
        if (
            (locked_teacher.role != 'teacher' and not locked_teacher.is_superuser)
            or not locked_teacher.is_active
        ):
            record_password_audit(
                event_type='reveal', outcome='denied',
                reason_code='teacher_role_changed', actor_user_id=teacher.pk,
                target_user_id=student_id, source_ip=source_ip,
            )
            failure = TeacherAuthorizationChanged()
        else:
            cutoff = timezone.now() - timedelta(minutes=1)
            recent_attempts = PasswordSecurityAudit.objects.filter(
                actor_user_id=teacher.pk,
                event_type='reveal',
                created_at__gte=cutoff,
            ).count()
            if recent_attempts >= settings.PASSWORD_REVEAL_LIMIT:
                record_password_audit(
                    event_type='reveal', outcome='rate_limited',
                    reason_code='per_teacher_minute_limit', actor_user_id=teacher.pk,
                    target_user_id=student_id, source_ip=source_ip,
                )
                failure = PasswordRevealRateLimited()
            else:
                student, scope_error = _authorized_student(locked_teacher, student_id)
                if scope_error:
                    record_password_audit(
                        event_type='reveal',
                        outcome='not_found' if scope_error == 'student_not_found' else 'denied',
                        reason_code=scope_error, actor_user_id=teacher.pk,
                        target_user_id=student_id, source_ip=source_ip,
                    )
                    failure = (
                        StudentTargetNotFound() if scope_error == 'student_not_found'
                        else TeacherAuthorizationChanged()
                    )
                elif (
                    student.password_recovery_status != 'available'
                    or not student.encrypted_password
                    or not student.password_encryption_key_id
                ):
                    record_password_audit(
                        event_type='reveal', outcome='unavailable',
                        reason_code='recovery_status_unavailable',
                        actor_user_id=teacher.pk, target_user_id=student_id,
                        source_ip=source_ip,
                    )
                    failure = StudentPasswordUnavailable()
                else:
                    try:
                        plaintext = StudentPasswordCipher(
                            settings.STUDENT_PASSWORD_KEY_CONFIG
                        ).decrypt(
                            student.encrypted_password,
                            student.password_encryption_key_id,
                        )
                    except PasswordEncryptionError:
                        record_password_audit(
                            event_type='reveal', outcome='unavailable',
                            reason_code='decrypt_failed', actor_user_id=teacher.pk,
                            target_user_id=student_id, source_ip=source_ip,
                        )
                        failure = StudentPasswordUnavailable()
                    if plaintext is not None and not student.check_password(plaintext):
                        plaintext = None
                        record_password_audit(
                            event_type='reveal', outcome='unavailable',
                            reason_code='hash_mismatch_runtime', actor_user_id=teacher.pk,
                            target_user_id=student_id, source_ip=source_ip,
                        )
                        failure = StudentPasswordUnavailable()
                    if plaintext is not None:
                        record_password_audit(
                            event_type='reveal', outcome='success',
                            reason_code='revealed', actor_user_id=teacher.pk,
                            target_user_id=student_id, source_ip=source_ip,
                        )
    if failure:
        raise failure
    return plaintext


def generate_temporary_password(length=12):
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789'
    while True:
        value = ''.join(secrets.choice(alphabet) for _ in range(length))
        if any(char in string.ascii_letters for char in value) and any(
            char in string.digits for char in value
        ):
            return value


def reset_student_password(
    *, teacher, student_id, mode, plaintext=None, source_ip=None
):
    event_type = 'generated_reset' if mode == 'generated' else 'manual_reset'
    failure = None
    generated_value = None
    with transaction.atomic():
        locked_teacher = CustomUser.objects.select_for_update().get(pk=teacher.pk)
        if (
            (locked_teacher.role != 'teacher' and not locked_teacher.is_superuser)
            or not locked_teacher.is_active
        ):
            record_password_audit(
                event_type=event_type, outcome='denied',
                reason_code='teacher_role_changed', actor_user_id=teacher.pk,
                target_user_id=student_id, source_ip=source_ip,
            )
            failure = TeacherAuthorizationChanged()
        else:
            student, scope_error = _authorized_student(locked_teacher, student_id)
            if scope_error:
                record_password_audit(
                    event_type=event_type,
                    outcome='not_found' if scope_error == 'student_not_found' else 'denied',
                    reason_code=scope_error, actor_user_id=teacher.pk,
                    target_user_id=student_id, source_ip=source_ip,
                )
                failure = (
                    StudentTargetNotFound() if scope_error == 'student_not_found'
                    else TeacherAuthorizationChanged()
                )
            else:
                candidate = generate_temporary_password() if mode == 'generated' else plaintext
                try:
                    set_student_password(
                        student, candidate, validate=True, invalidate_tokens=True
                    )
                except ValidationError:
                    record_password_audit(
                        event_type=event_type, outcome='denied',
                        reason_code='password_validation_failed',
                        actor_user_id=teacher.pk, target_user_id=student_id,
                        source_ip=source_ip,
                    )
                    failure = ValidationError('新密码不符合安全要求。')
                if failure is None:
                    record_password_audit(
                        event_type=event_type, outcome='success',
                        reason_code='password_reset', actor_user_id=teacher.pk,
                        target_user_id=student_id, source_ip=source_ip,
                    )
                    if mode == 'generated':
                        generated_value = candidate
                del candidate
    if failure:
        raise failure
    return generated_value
