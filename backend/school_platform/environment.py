"""Environment parsing and production safety checks."""

import os
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured


VALID_ENVIRONMENTS = {'development', 'test', 'production'}
TRUE_VALUES = {'1', 'true', 'yes', 'on'}
FALSE_VALUES = {'0', 'false', 'no', 'off'}


def _source(environ=None):
    return os.environ if environ is None else environ


def get_environment(environ=None):
    value = _source(environ).get('DJANGO_ENV', 'development').strip().lower()
    if value not in VALID_ENVIRONMENTS:
        choices = ', '.join(sorted(VALID_ENVIRONMENTS))
        raise ImproperlyConfigured(f'DJANGO_ENV 必须是以下值之一：{choices}')
    return value


def get_bool(name, default=False, environ=None):
    raw_value = _source(environ).get(name)
    if raw_value is None or not raw_value.strip():
        return default

    value = raw_value.strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    raise ImproperlyConfigured(
        f'{name} 必须使用 true/false、1/0、yes/no 或 on/off。'
    )


def get_list(name, default=(), environ=None):
    raw_value = _source(environ).get(name)
    if raw_value is None:
        return list(default)
    return [item.strip() for item in raw_value.split(',') if item.strip()]


def get_int(name, default, *, minimum=None, maximum=None, environ=None):
    raw_value = _source(environ).get(name)
    if raw_value is None or not raw_value.strip():
        value = default
    else:
        try:
            value = int(raw_value.strip())
        except ValueError as exc:
            raise ImproperlyConfigured(f'{name} 必须是整数。') from exc

    if minimum is not None and value < minimum:
        raise ImproperlyConfigured(f'{name} 不能小于 {minimum}。')
    if maximum is not None and value > maximum:
        raise ImproperlyConfigured(f'{name} 不能大于 {maximum}。')
    return value


def _is_https_origin(value):
    parsed = urlparse(value)
    return parsed.scheme == 'https' and bool(parsed.netloc) and not parsed.path.strip('/')


def validate_production_settings(
    *,
    environment,
    secret_key,
    debug,
    allowed_hosts,
    cors_allowed_origins,
    csrf_trusted_origins,
    development_secret_key,
    database_engine='sqlite',
):
    if environment != 'production':
        return

    errors = []
    if not secret_key or secret_key == development_secret_key or len(secret_key) < 32:
        errors.append('DJANGO_SECRET_KEY 必须显式设置为至少 32 位的生产密钥')
    if debug:
        errors.append('生产环境必须设置 DJANGO_DEBUG=false')
    if database_engine != 'mysql':
        errors.append('生产环境必须设置 DJANGO_DB_ENGINE=mysql')
    if not allowed_hosts:
        errors.append('生产环境必须设置 DJANGO_ALLOWED_HOSTS')
    elif '*' in allowed_hosts:
        errors.append('DJANGO_ALLOWED_HOSTS 不能包含通配符 *')

    invalid_cors = [origin for origin in cors_allowed_origins if not _is_https_origin(origin)]
    if invalid_cors:
        errors.append('DJANGO_CORS_ALLOWED_ORIGINS 在生产环境只能包含 HTTPS 来源')

    invalid_csrf = [origin for origin in csrf_trusted_origins if not _is_https_origin(origin)]
    if invalid_csrf:
        errors.append('DJANGO_CSRF_TRUSTED_ORIGINS 在生产环境只能包含 HTTPS 来源')

    if errors:
        raise ImproperlyConfigured('；'.join(errors))
