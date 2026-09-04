import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from platform_ops.migration_data import utc_now, write_private_json
from users.models import CustomUser, PasswordSecurityAudit
from users.security import PasswordEncryptionError, StudentPasswordCipher


class Command(BaseCommand):
    help = '核验阶段 3 学生密码加密迁移并生成脱敏报告'

    def add_arguments(self, parser):
        parser.add_argument('--report', required=True)

    def handle(self, *args, **options):
        artifacts_root = (settings.BASE_DIR / 'migration_artifacts').resolve()
        report_path = Path(options['report']).expanduser()
        if not report_path.is_absolute():
            report_path = (settings.BASE_DIR / report_path).resolve()
        else:
            report_path = report_path.resolve()
        if artifacts_root not in report_path.parents:
            raise CommandError('验证报告必须写入 migration_artifacts 下。')
        if report_path.exists():
            raise CommandError('验证报告已存在，拒绝覆盖。')

        try:
            cipher = StudentPasswordCipher(settings.STUDENT_PASSWORD_KEY_CONFIG)
        except PasswordEncryptionError as exc:
            raise CommandError(str(exc)) from exc

        students = CustomUser.objects.filter(role='student')
        status_counts = {
            status: students.filter(password_recovery_status=status).count()
            for status in (
                'available', 'missing_legacy', 'hash_mismatch', 'not_applicable'
            )
        }
        checked = 0
        valid = 0
        for user in students.filter(password_recovery_status='available').iterator():
            checked += 1
            try:
                plaintext = cipher.decrypt(
                    user.encrypted_password, user.password_encryption_key_id
                )
            except PasswordEncryptionError:
                continue
            if user.check_password(plaintext):
                valid += 1
            del plaintext

        teacher_ciphertext_count = CustomUser.objects.exclude(role='student').filter(
            encrypted_password__isnull=False
        ).exclude(encrypted_password='').count()
        with connection.cursor() as cursor:
            columns = {
                column.name
                for column in connection.introspection.get_table_description(
                    cursor, CustomUser._meta.db_table
                )
            }
        constraints_ok = True
        try:
            connection.check_constraints()
        except Exception:
            constraints_ok = False

        forbidden_audit_fields = {
            'password', 'plaintext', 'ciphertext', 'token', 'request_body'
        }
        audit_fields = {field.name for field in PasswordSecurityAudit._meta.fields}
        checks = {
            'plain_password_column_removed': 'plain_password' not in columns,
            'available_passwords_valid': checked == valid,
            'teacher_ciphertext_absent': teacher_ciphertext_count == 0,
            'constraints': constraints_ok,
            'audit_schema_safe': not (audit_fields & forbidden_audit_fields),
        }
        result = {
            'report_version': 1,
            'created_at': utc_now(),
            'status': 'ok' if all(checks.values()) else 'failed',
            'database_vendor': connection.vendor,
            'checks': checks,
            'student_count': students.count(),
            'recovery_status_counts': status_counts,
            'recoverable_password_checked_count': checked,
            'recoverable_password_valid_count': valid,
            'teacher_ciphertext_count': teacher_ciphertext_count,
            'audit_count': PasswordSecurityAudit.objects.count(),
        }
        report_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(report_path.parent, 0o700)
        write_private_json(report_path, result)
        if result['status'] != 'ok':
            raise CommandError('阶段 3 密码迁移核验失败，请查看脱敏报告。')

        self.stdout.write(self.style.SUCCESS('阶段 3 密码迁移核验通过'))
        self.stdout.write(f'可恢复密码校验：{valid}/{checked}')
        self.stdout.write(f'脱敏报告：{report_path}')
