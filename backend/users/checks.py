"""Django system checks for student password security configuration."""

from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security)
def student_password_key_check(app_configs, **kwargs):
    if settings.STUDENT_PASSWORD_KEY_CONFIG.configured:
        return []
    return [
        Error(
            '学生密码加密服务尚未配置。',
            hint='先执行 scripts/stage3_security_local.sh init，生产环境使用安全注入的环境变量。',
            id='users.E001',
        )
    ]
