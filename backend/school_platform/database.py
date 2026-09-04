"""Database configuration parsing for SQLite and MySQL."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


SUPPORTED_DATABASE_ENGINES = {'sqlite', 'mysql'}


def _source(environ=None):
    return os.environ if environ is None else environ


def get_database_engine(environ=None):
    value = _source(environ).get('DJANGO_DB_ENGINE', 'sqlite').strip().lower()
    if value not in SUPPORTED_DATABASE_ENGINES:
        raise ImproperlyConfigured('DJANGO_DB_ENGINE 必须是 sqlite 或 mysql')
    return value


def get_non_negative_int(name, default, environ=None, *, maximum=None):
    raw_value = _source(environ).get(name)
    if raw_value is None or not raw_value.strip():
        value = default
    else:
        try:
            value = int(raw_value.strip())
        except ValueError as exc:
            raise ImproperlyConfigured(f'{name} 必须是整数') from exc

    if value < 0:
        raise ImproperlyConfigured(f'{name} 不能小于 0')
    if maximum is not None and value > maximum:
        raise ImproperlyConfigured(f'{name} 不能大于 {maximum}')
    return value


def validate_database_settings(*, environment, engine, config):
    if environment == 'production' and engine != 'mysql':
        raise ImproperlyConfigured('生产环境必须设置 DJANGO_DB_ENGINE=mysql')

    if engine != 'mysql':
        return

    variable_names = {
        'NAME': 'DJANGO_DB_NAME',
        'USER': 'DJANGO_DB_USER',
        'PASSWORD': 'DJANGO_DB_PASSWORD',
        'HOST': 'DJANGO_DB_HOST',
    }
    missing = [variable for key, variable in variable_names.items() if not config.get(key)]
    if missing:
        raise ImproperlyConfigured(f'MySQL 配置缺少：{", ".join(missing)}')

    port = config.get('PORT')
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise ImproperlyConfigured('DJANGO_DB_PORT 必须在 1 到 65535 之间')


def build_database_settings(base_dir, environment, environ=None):
    source = _source(environ)
    engine = get_database_engine(source)
    base_dir = Path(base_dir)

    if engine == 'sqlite':
        configured_name = source.get('DJANGO_DB_NAME', '').strip()
        config = {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': Path(configured_name).expanduser() if configured_name else base_dir / 'db.sqlite3',
        }
        validate_database_settings(environment=environment, engine=engine, config=config)
        return config

    port = get_non_negative_int('DJANGO_DB_PORT', 3306, source, maximum=65535)
    if port == 0:
        raise ImproperlyConfigured('DJANGO_DB_PORT 必须在 1 到 65535 之间')
    connect_timeout = get_non_negative_int('DJANGO_DB_CONNECT_TIMEOUT', 5, source)
    conn_max_age = get_non_negative_int('DJANGO_DB_CONN_MAX_AGE', 60, source)

    name = source.get('DJANGO_DB_NAME', '').strip()
    test_name = source.get('DJANGO_DB_TEST_NAME', '').strip() or (f'test_{name}' if name else '')
    config = {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': name,
        'USER': source.get('DJANGO_DB_USER', '').strip(),
        'PASSWORD': source.get('DJANGO_DB_PASSWORD', ''),
        'HOST': source.get('DJANGO_DB_HOST', '').strip(),
        'PORT': port,
        'CONN_MAX_AGE': conn_max_age,
        'OPTIONS': {
            'charset': 'utf8mb4',
            'connect_timeout': connect_timeout,
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION'",
            'isolation_level': 'read committed',
        },
        'TEST': {'NAME': test_name},
    }
    validate_database_settings(environment=environment, engine=engine, config=config)
    return config
