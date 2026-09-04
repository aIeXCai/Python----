import json
import os
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from platform_ops.migration_data import (
    compare_summary,
    database_summary,
    mysql_server_version,
    utc_now,
    validate_local_mysql_target,
    validate_manifest,
    write_private_json,
)
from users.security import PasswordEncryptionError, StudentPasswordCipher


class Command(BaseCommand):
    help = '校验本地 MySQL 迁移结果并生成脱敏报告'

    def add_arguments(self, parser):
        parser.add_argument('--manifest', required=True)
        parser.add_argument('--report', required=True)

    def handle(self, *args, **options):
        config = connection.settings_dict
        try:
            validate_local_mysql_target(
                connection.vendor,
                config.get('HOST'),
                config.get('PORT'),
                config.get('NAME'),
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        artifacts_root = (settings.BASE_DIR / 'migration_artifacts').resolve()
        manifest_path = Path(options['manifest']).expanduser().resolve()
        report_path = Path(options['report']).expanduser().resolve()
        if artifacts_root not in manifest_path.parents or not manifest_path.is_file():
            raise CommandError('manifest 必须位于 migration_artifacts 下且真实存在')
        if artifacts_root not in report_path.parents:
            raise CommandError('验证报告必须写入 migration_artifacts 下')
        if report_path.exists():
            raise CommandError('验证报告已存在，拒绝覆盖')

        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        try:
            validate_manifest(manifest)
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        version = mysql_server_version()
        version_ok = version.startswith('8.0.')
        actual, _ = database_summary()
        mismatches = compare_summary(manifest, actual)

        User = apps.get_model('users', 'CustomUser')
        Token = apps.get_model('authtoken', 'Token')
        password_candidates = User.objects.filter(
            role='student', password_recovery_status='available'
        )
        password_checked = password_candidates.count()
        password_valid = 0
        cipher = StudentPasswordCipher(settings.STUDENT_PASSWORD_KEY_CONFIG)
        for user in password_candidates.iterator():
            try:
                plaintext = cipher.decrypt(
                    user.encrypted_password, user.password_encryption_key_id
                )
            except PasswordEncryptionError:
                continue
            if user.check_password(plaintext):
                password_valid += 1
            del plaintext
        token_count = Token.objects.count()
        token_non_empty = Token.objects.exclude(key='').count()

        constraint_ok = True
        try:
            connection.check_constraints()
        except Exception:
            constraint_ok = False

        checks = {
            'mysql_8_0': version_ok,
            'summary_matches': not mismatches,
            'constraints': constraint_ok,
            'password_hash_checks': password_checked == password_valid,
            'token_non_empty_checks': token_count == token_non_empty,
        }
        status = 'ok' if all(checks.values()) else 'failed'
        report = {
            'report_version': 3,
            'created_at': utc_now(),
            'status': status,
            'database_vendor': connection.vendor,
            'database_version': version,
            'checks': checks,
            'mismatched_sections': mismatches,
            'password_hash_checked_count': password_checked,
            'password_hash_valid_count': password_valid,
            'token_checked_count': token_count,
            'token_non_empty_count': token_non_empty,
            'expected_overall_sha256': manifest['overall_sha256'],
            'actual_overall_sha256': actual['overall_sha256'],
        }
        report_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(report_path.parent, 0o700)
        write_private_json(report_path, report)

        if status != 'ok':
            raise CommandError('MySQL 迁移验证失败，请查看脱敏报告')

        self.stdout.write(self.style.SUCCESS('MySQL 迁移完整性验证通过'))
        self.stdout.write(f'服务端版本：{version}')
        self.stdout.write(f'密码哈希抽查：{password_valid}/{password_checked}')
        self.stdout.write(f'Token 非空抽查：{token_non_empty}/{token_count}')
        self.stdout.write(f'脱敏报告：{report_path}')
