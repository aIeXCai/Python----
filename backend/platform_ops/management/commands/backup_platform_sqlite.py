import os
import sqlite3
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from platform_ops.migration_data import (
    migration_models,
    sha256_file,
    utc_now,
    write_private_json,
)


def sqlite_checks(sqlite_connection):
    integrity_rows = [row[0] for row in sqlite_connection.execute('PRAGMA integrity_check')]
    foreign_key_rows = sqlite_connection.execute('PRAGMA foreign_key_check').fetchall()
    return integrity_rows, foreign_key_rows


class Command(BaseCommand):
    help = '创建只读一致性 SQLite 备份和脱敏 manifest'

    def add_arguments(self, parser):
        parser.add_argument('--output-dir', required=True)

    def handle(self, *args, **options):
        if connection.vendor != 'sqlite':
            raise CommandError('backup_platform_sqlite 只允许 SQLite 源数据库')

        source_path = Path(connection.settings_dict['NAME']).expanduser().resolve()
        if not source_path.is_file():
            raise CommandError('SQLite 源数据库不存在')

        artifacts_root = (settings.BASE_DIR / 'migration_artifacts').resolve()
        output_dir = Path(options['output_dir']).expanduser().resolve()
        if artifacts_root != output_dir and artifacts_root not in output_dir.parents:
            raise CommandError('备份目录必须位于 backend/migration_artifacts 下')
        if output_dir.exists():
            raise CommandError('备份目录已存在，拒绝覆盖')
        output_dir.mkdir(parents=True, mode=0o700)
        os.chmod(output_dir, 0o700)

        source_sha_before = sha256_file(source_path)
        uri = f"file:{quote(str(source_path), safe='/')}?mode=ro"
        backup_path = output_dir / 'source.sqlite3'

        try:
            with sqlite3.connect(uri, uri=True) as source:
                integrity, foreign_keys = sqlite_checks(source)
                if integrity != ['ok']:
                    raise CommandError('SQLite 源数据库 integrity_check 失败')
                if foreign_keys:
                    raise CommandError('SQLite 源数据库 foreign_key_check 失败')
                with sqlite3.connect(backup_path) as destination:
                    source.backup(destination)

            os.chmod(backup_path, 0o600)
            with sqlite3.connect(f"file:{quote(str(backup_path), safe='/')}?mode=ro", uri=True) as backup:
                backup_integrity, backup_foreign_keys = sqlite_checks(backup)
            if backup_integrity != ['ok'] or backup_foreign_keys:
                raise CommandError('SQLite 备份完整性检查失败')

            source_sha_after = sha256_file(source_path)
            if source_sha_before != source_sha_after:
                raise CommandError('备份期间源 SQLite 文件发生变化，请停止写入后重试')

            model_counts = {
                model._meta.label_lower: model._default_manager.count()
                for model in migration_models()
            }
            manifest = {
                'manifest_version': 1,
                'created_at': utc_now(),
                'sqlite_version': sqlite3.sqlite_version,
                'source_path': str(source_path),
                'source_size': source_path.stat().st_size,
                'source_sha256_before': source_sha_before,
                'source_sha256_after': source_sha_after,
                'backup_path': str(backup_path),
                'backup_size': backup_path.stat().st_size,
                'backup_sha256': sha256_file(backup_path),
                'integrity_check': 'ok',
                'foreign_key_violations': 0,
                'model_counts': model_counts,
            }
            manifest_path = output_dir / 'backup-manifest.json'
            write_private_json(manifest_path, manifest)
        except Exception:
            if backup_path.exists():
                backup_path.unlink()
            raise

        self.stdout.write(self.style.SUCCESS('SQLite 一致性备份完成'))
        self.stdout.write(f'备份目录：{output_dir}')
        for label, count in model_counts.items():
            self.stdout.write(f'  {label}: {count}')
