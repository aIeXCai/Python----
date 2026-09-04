import json
from pathlib import Path

from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connection, transaction

from platform_ops.migration_data import (
    assert_business_tables_empty,
    compare_summary,
    database_summary,
    migration_models,
    sha256_file,
    validate_local_mysql_target,
    validate_manifest,
)


class Command(BaseCommand):
    help = '将受校验的业务 fixture 导入空的本地 MySQL stage2 数据库'

    def add_arguments(self, parser):
        parser.add_argument('--fixture', required=True)
        parser.add_argument('--manifest', required=True)

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

        fixture_path = Path(options['fixture']).expanduser().resolve()
        manifest_path = Path(options['manifest']).expanduser().resolve()
        artifacts_root = (settings.BASE_DIR / 'migration_artifacts').resolve()
        for path in (fixture_path, manifest_path):
            if artifacts_root not in path.parents:
                raise CommandError('fixture 和 manifest 必须位于 migration_artifacts 下')
            if not path.is_file():
                raise CommandError(f'文件不存在：{path.name}')

        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        try:
            validate_manifest(manifest)
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        if sha256_file(fixture_path) != manifest['fixture_sha256']:
            raise CommandError('fixture SHA-256 与 manifest 不一致')

        try:
            assert_business_tables_empty()
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        fixture_content = fixture_path.read_text(encoding='utf-8')
        deserialized_objects = []
        try:
            with transaction.atomic():
                with connection.constraint_checks_disabled():
                    for item in serializers.deserialize(
                        'json',
                        fixture_content,
                        handle_forward_references=True,
                    ):
                        item.save()
                        deserialized_objects.append(item)
                    for item in deserialized_objects:
                        if item.deferred_fields:
                            item.save_deferred_fields()

                connection.check_constraints()
                sequence_sql = connection.ops.sequence_reset_sql(no_style(), migration_models())
                with connection.cursor() as cursor:
                    for statement in sequence_sql:
                        cursor.execute(statement)

                actual, _ = database_summary()
                mismatches = compare_summary(manifest, actual)
                if mismatches:
                    raise CommandError(
                        f'导入后摘要不一致：{", ".join(mismatches)}'
                    )
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(f'业务数据导入失败：{exc.__class__.__name__}') from exc

        self.stdout.write(self.style.SUCCESS('MySQL 业务数据导入和即时摘要校验通过'))
        for label, model_summary in actual['models'].items():
            self.stdout.write(f"  {label}: {model_summary['count']}")
