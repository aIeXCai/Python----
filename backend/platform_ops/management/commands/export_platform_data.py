import json
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from platform_ops.migration_data import (
    MANIFEST_VERSION,
    database_summary,
    sha256_file,
    utc_now,
    write_private_bytes,
    write_private_json,
)


class Command(BaseCommand):
    help = '从 SQLite 一致性快照导出有序业务 fixture 和脱敏摘要'

    def add_arguments(self, parser):
        parser.add_argument('--output-dir', required=True)

    def handle(self, *args, **options):
        if connection.vendor != 'sqlite':
            raise CommandError('export_platform_data 只允许 SQLite 快照源')

        source_path = Path(connection.settings_dict['NAME']).expanduser().resolve()
        original_path = (settings.BASE_DIR / 'db.sqlite3').resolve()
        if source_path == original_path:
            raise CommandError('拒绝直接从原始 db.sqlite3 导出，请先创建一致性备份')
        if not source_path.is_file():
            raise CommandError('SQLite 快照不存在')

        output_dir = Path(options['output_dir']).expanduser().resolve()
        artifacts_root = (settings.BASE_DIR / 'migration_artifacts').resolve()
        if artifacts_root != output_dir and artifacts_root not in output_dir.parents:
            raise CommandError('导出目录必须位于 backend/migration_artifacts 下')
        if not output_dir.is_dir():
            raise CommandError('导出目录不存在，请先执行 backup_platform_sqlite')

        fixture_path = output_dir / 'platform-data.json'
        manifest_path = output_dir / 'data-manifest.json'
        if fixture_path.exists() or manifest_path.exists():
            raise CommandError('导出文件已存在，拒绝覆盖')

        summary, all_records = database_summary()
        fixture_bytes = (
            json.dumps(all_records, ensure_ascii=False, indent=2, sort_keys=True).encode('utf-8')
            + b'\n'
        )
        write_private_bytes(fixture_path, fixture_bytes)
        os.chmod(fixture_path, 0o600)

        manifest = {
            'manifest_version': MANIFEST_VERSION,
            'created_at': utc_now(),
            'source_vendor': connection.vendor,
            'source_snapshot': str(source_path),
            'source_snapshot_sha256': sha256_file(source_path),
            'fixture_file': fixture_path.name,
            'fixture_sha256': sha256_file(fixture_path),
            **summary,
        }
        write_private_json(manifest_path, manifest)

        self.stdout.write(self.style.SUCCESS('SQLite 业务数据导出完成'))
        self.stdout.write(f'导出目录：{output_dir}')
        for label, model_summary in summary['models'].items():
            self.stdout.write(f"  {label}: {model_summary['count']}")
