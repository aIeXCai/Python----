"""Shared, deterministic helpers for the SQLite-to-MySQL migration."""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from django.apps import apps
from django.core import serializers
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder


MANIFEST_VERSION = 3
MODEL_LABELS = (
    'auth.Group',
    'users.CustomUser',
    'users.PasswordSecurityAudit',
    'authtoken.Token',
    'ai_courses.Problem',
    'info_tech.Unit',
    'ai_courses.Submission',
    'info_tech.Question',
    'info_tech.QuizSession',
    'info_tech.QuizSubmission',
    'chat.ChatSession',
    'chat.ChatMessage',
)
LOCAL_MYSQL_HOST = '127.0.0.1'
LOCAL_MYSQL_PORT = 3308
LOCAL_MYSQL_DATABASE = 'python_learning_stage2'


def migration_models():
    return tuple(apps.get_model(label) for label in MODEL_LABELS)


def canonical_json(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    ).encode('utf-8')


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_private_bytes(path, content):
    path = Path(path)
    temporary = path.with_name(f'.{path.name}.tmp')
    temporary.write_bytes(content)
    os.chmod(temporary, 0o600)
    temporary.replace(path)
    os.chmod(path, 0o600)


def write_private_json(path, value):
    content = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode('utf-8')
    write_private_bytes(path, content + b'\n')


def serialize_records():
    records_by_model = {}
    all_records = []
    for model in migration_models():
        queryset = model._default_manager.order_by(model._meta.pk.name)
        records = json.loads(
            serializers.serialize(
                'json',
                queryset,
                use_natural_foreign_keys=True,
                use_natural_primary_keys=False,
            )
        )
        label = model._meta.label_lower
        records_by_model[label] = records
        all_records.extend(records)
    return records_by_model, all_records


def model_summaries(records_by_model):
    summaries = {}
    for label, records in records_by_model.items():
        primary_keys = [record['pk'] for record in records]
        summaries[label] = {
            'count': len(records),
            'pk_sha256': sha256_bytes(canonical_json(primary_keys)),
            'content_sha256': sha256_bytes(canonical_json(records)),
        }
    return summaries


def relation_counts():
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('users', 'CustomUser')
    QuizSession = apps.get_model('info_tech', 'QuizSession')
    return {
        'auth.group.permissions': Group.permissions.through.objects.count(),
        'users.customuser.groups': User.groups.through.objects.count(),
        'users.customuser.user_permissions': User.user_permissions.through.objects.count(),
        'info_tech.quizsession.units': QuizSession.units.through.objects.count(),
    }


def applied_migrations():
    return [
        f'{app}.{name}'
        for app, name in MigrationRecorder.Migration.objects.order_by('app', 'name').values_list(
            'app', 'name'
        )
    ]


def database_summary():
    records_by_model, all_records = serialize_records()
    models = model_summaries(records_by_model)
    relations = relation_counts()
    migrations = applied_migrations()
    overall_payload = {
        'models': models,
        'relations': relations,
        'migrations': migrations,
    }
    return {
        **overall_payload,
        'overall_sha256': sha256_bytes(canonical_json(overall_payload)),
    }, all_records


def validate_manifest(manifest):
    if manifest.get('manifest_version') != MANIFEST_VERSION:
        raise ImproperlyConfigured('不支持的数据 manifest 版本')
    for key in ('fixture_sha256', 'models', 'relations', 'migrations', 'overall_sha256'):
        if key not in manifest:
            raise ImproperlyConfigured(f'数据 manifest 缺少字段：{key}')


def compare_summary(manifest, actual):
    mismatches = []
    for key in ('models', 'relations', 'migrations', 'overall_sha256'):
        if manifest.get(key) != actual.get(key):
            mismatches.append(key)
    return mismatches


def validate_local_mysql_target(vendor, host, port, name):
    if vendor != 'mysql':
        raise ImproperlyConfigured('导入和验证目标必须是 MySQL')
    if host != LOCAL_MYSQL_HOST or int(port) != LOCAL_MYSQL_PORT:
        raise ImproperlyConfigured('阶段 2 只允许本机 127.0.0.1:3308 MySQL 目标')
    if name != LOCAL_MYSQL_DATABASE:
        raise ImproperlyConfigured('阶段 2 只允许 python_learning_stage2 目标库')


def assert_business_tables_empty():
    non_empty = [
        model._meta.label_lower
        for model in migration_models()
        if model._default_manager.exists()
    ]
    if non_empty:
        raise ImproperlyConfigured(f'目标业务表不是空库：{", ".join(non_empty)}')


def mysql_server_version():
    with connection.cursor() as cursor:
        cursor.execute('SELECT VERSION()')
        return cursor.fetchone()[0]
