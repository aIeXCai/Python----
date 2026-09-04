"""
Django settings for school_platform project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

from .database import build_database_settings, get_database_engine
from .environment import (
    get_bool,
    get_environment,
    get_int,
    get_list,
    validate_production_settings,
)

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env.security.local')
load_dotenv(BASE_DIR / '.env')

ENVIRONMENT = get_environment()
DEVELOPMENT_SECRET_KEY = 'django-insecure-development-only-change-me'
TEST_SECRET_KEY = 'django-insecure-test-environment-only'

if ENVIRONMENT == 'production':
    default_secret_key = ''
elif ENVIRONMENT == 'test':
    default_secret_key = TEST_SECRET_KEY
else:
    default_secret_key = DEVELOPMENT_SECRET_KEY

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', default_secret_key)
DEBUG = get_bool('DJANGO_DEBUG', default=ENVIRONMENT == 'development')

default_hosts = {
    'development': ('localhost', '127.0.0.1', '[::1]'),
    'test': ('testserver', 'localhost'),
    'production': (),
}[ENVIRONMENT]
ALLOWED_HOSTS = get_list('DJANGO_ALLOWED_HOSTS', default=default_hosts)
CORS_ALLOWED_ORIGINS = get_list('DJANGO_CORS_ALLOWED_ORIGINS')
CSRF_TRUSTED_ORIGINS = get_list('DJANGO_CSRF_TRUSTED_ORIGINS')
CORS_ALLOW_ALL_ORIGINS = False
DATABASE_ENGINE = get_database_engine()

from users.security import parse_password_key_config  # noqa: E402

STUDENT_PASSWORD_KEY_CONFIG = parse_password_key_config(
    os.environ.get('DJANGO_STUDENT_PASSWORD_KEYS', ''),
    os.environ.get('DJANGO_STUDENT_PASSWORD_PRIMARY_KEY_ID', ''),
)
TOKEN_TTL_HOURS = get_int('DJANGO_TOKEN_TTL_HOURS', 12, minimum=1, maximum=720)
PASSWORD_REVEAL_LIMIT = get_int('DJANGO_PASSWORD_REVEAL_LIMIT', 30, minimum=1, maximum=300)
PASSWORD_REVEAL_SECONDS = get_int('DJANGO_PASSWORD_REVEAL_SECONDS', 30, minimum=5, maximum=300)

# Student code is only queued by Django. It is never executed in a Web worker.
CODE_EXECUTION_ENABLED = get_bool(
    'CODE_EXECUTION_ENABLED',
    default=ENVIRONMENT != 'production',
)
EXECUTION_CODE_MAX_BYTES = get_int(
    'EXECUTION_CODE_MAX_BYTES', 65536, minimum=1, maximum=1048576,
)
EXECUTION_STDIN_MAX_BYTES = get_int(
    'EXECUTION_STDIN_MAX_BYTES', 65536, minimum=0, maximum=1048576,
)
EXECUTION_TEST_CASE_MAX_BYTES = get_int(
    'EXECUTION_TEST_CASE_MAX_BYTES', 65536, minimum=1, maximum=1048576,
)
EXECUTION_TEST_CASES_MAX = get_int(
    'EXECUTION_TEST_CASES_MAX', 100, minimum=1, maximum=1000,
)
EXECUTION_USER_RUNNING_LIMIT = get_int(
    'EXECUTION_USER_RUNNING_LIMIT', 1, minimum=1, maximum=20,
)
EXECUTION_USER_QUEUED_LIMIT = get_int(
    'EXECUTION_USER_QUEUED_LIMIT', 2, minimum=1, maximum=100,
)
EXECUTION_QUEUE_TTL_SECONDS = get_int(
    'EXECUTION_QUEUE_TTL_SECONDS', 120, minimum=10, maximum=3600,
)
EXECUTION_LEASE_SECONDS = get_int(
    'EXECUTION_LEASE_SECONDS', 30, minimum=10, maximum=300,
)
EXECUTION_MAX_ATTEMPTS = get_int(
    'EXECUTION_MAX_ATTEMPTS', 2, minimum=1, maximum=10,
)
EXECUTION_MAX_OUTPUT_BYTES = get_int(
    'EXECUTION_MAX_OUTPUT_BYTES', 131072, minimum=1024, maximum=1048576,
)
EXECUTION_MAX_RESULT_BYTES = get_int(
    'EXECUTION_MAX_RESULT_BYTES', 262144, minimum=1024, maximum=2097152,
)
RUNNER_PROTOCOL_VERSION = os.environ.get('RUNNER_PROTOCOL_VERSION', 'runner.v1').strip()
RUNNER_SERVICE_SECRET = os.environ.get('RUNNER_SERVICE_SECRET', '')
RUNNER_CLOCK_SKEW_SECONDS = get_int(
    'RUNNER_CLOCK_SKEW_SECONDS', 60, minimum=10, maximum=300,
)
RUNNER_RECEIPT_TTL_SECONDS = get_int(
    'RUNNER_RECEIPT_TTL_SECONDS', 86400, minimum=300, maximum=604800,
)
RUNNER_NODE_STALE_SECONDS = get_int(
    'RUNNER_NODE_STALE_SECONDS', 30, minimum=10, maximum=300,
)

if ENVIRONMENT == 'production' and CODE_EXECUTION_ENABLED:
    from django.core.exceptions import ImproperlyConfigured

    if len(RUNNER_SERVICE_SECRET) < 32 or RUNNER_SERVICE_SECRET.startswith('replace-'):
        raise ImproperlyConfigured(
            '生产环境启用代码执行时，RUNNER_SERVICE_SECRET 必须是至少 32 位的独立密钥。'
        )

if ENVIRONMENT == 'production' and not STUDENT_PASSWORD_KEY_CONFIG.configured:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(
        '生产环境必须配置有效的学生密码加密密钥和主密钥 ID。'
    )

validate_production_settings(
    environment=ENVIRONMENT,
    secret_key=SECRET_KEY,
    debug=DEBUG,
    allowed_hosts=ALLOWED_HOSTS,
    cors_allowed_origins=CORS_ALLOWED_ORIGINS,
    csrf_trusted_origins=CSRF_TRUSTED_ORIGINS,
    development_secret_key=DEVELOPMENT_SECRET_KEY,
    database_engine=DATABASE_ENGINE,
)

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # 第三方
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    # 自定义 app
    'users',
    'ai_courses',
    'info_tech',
    'chat',
    'platform_ops',
    'execution',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # CORS 要在最前面
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'school_platform.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'school_platform.wsgi.application'

# Database
DATABASES = {
    'default': build_database_settings(BASE_DIR, ENVIRONMENT),
}

# 自定义用户模型
AUTH_USER_MODEL = 'users.CustomUser'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'users.authentication.ExpiringTokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
}

# Internationalization
LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files（上传的课件、quiz JSON等）
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# AI课题目目录（与 server.py 共用，在 backend/ 的上一层）
PROBLEMS_DIR = BASE_DIR.parent / 'problems'

# Submissions 目录

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Production security. Local development stays on HTTP; production is expected
# to run behind an HTTPS reverse proxy.
IS_PRODUCTION = ENVIRONMENT == 'production'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') if IS_PRODUCTION else None
SECURE_SSL_REDIRECT = get_bool('DJANGO_SECURE_SSL_REDIRECT', default=IS_PRODUCTION)
SESSION_COOKIE_SECURE = get_bool('DJANGO_SESSION_COOKIE_SECURE', default=IS_PRODUCTION)
CSRF_COOKIE_SECURE = get_bool('DJANGO_CSRF_COOKIE_SECURE', default=IS_PRODUCTION)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000 if IS_PRODUCTION else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = IS_PRODUCTION
SECURE_HSTS_PRELOAD = IS_PRODUCTION
X_FRAME_OPTIONS = 'DENY'

# Console logging is suitable for local terminals now and cloud log collection
# later. No request bodies, cookies, or authorization headers are logged.
LOG_LEVEL = os.environ.get(
    'DJANGO_LOG_LEVEL',
    'WARNING' if ENVIRONMENT == 'test' else 'INFO',
).strip().upper()
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '{asctime} {levelname} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': LOG_LEVEL,
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
    },
}

# MiniMax API 配置
MINIMAX_API_KEY = os.environ.get('MINIMAX_API_KEY', '')
MINIMAX_API_BASE = 'https://api.minimax.chat/v1'
MINIMAX_MODEL = 'minimax-m2.5'
