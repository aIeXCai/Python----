from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.db import migrations, models


def encrypt_legacy_passwords(apps, schema_editor):
    config = settings.STUDENT_PASSWORD_KEY_CONFIG
    if not config.configured:
        raise RuntimeError('学生密码加密服务未配置，拒绝迁移历史明文。')

    User = apps.get_model('users', 'CustomUser')
    key_id = config.primary_key_id
    fernet = Fernet(config.keys[key_id].encode('ascii'))
    users = list(User.objects.all().order_by('pk'))
    for user in users:
        user.encrypted_password = None
        user.password_encryption_key_id = None
        if user.role != 'student':
            user.password_recovery_status = 'not_applicable'
        elif not user.plain_password:
            user.password_recovery_status = 'missing_legacy'
        elif check_password(user.plain_password, user.password):
            user.encrypted_password = fernet.encrypt(
                user.plain_password.encode('utf-8')
            ).decode('ascii')
            user.password_encryption_key_id = key_id
            user.password_recovery_status = 'available'
        else:
            user.password_recovery_status = 'hash_mismatch'

    if users:
        User.objects.bulk_update(
            users,
            [
                'encrypted_password',
                'password_encryption_key_id',
                'password_recovery_status',
            ],
        )


class Migration(migrations.Migration):
    atomic = True

    dependencies = [
        ('users', '0005_add_display_name_plain_password'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='encrypted_password',
            field=models.TextField(blank=True, editable=False, null=True, verbose_name='学生密码密文'),
        ),
        migrations.AddField(
            model_name='customuser',
            name='password_encryption_key_id',
            field=models.CharField(blank=True, editable=False, max_length=40, null=True, verbose_name='学生密码密钥版本'),
        ),
        migrations.AddField(
            model_name='customuser',
            name='password_recovery_status',
            field=models.CharField(
                choices=[
                    ('available', '可安全查看'),
                    ('missing_legacy', '历史密码缺失'),
                    ('hash_mismatch', '历史密码与哈希不一致'),
                    ('not_applicable', '不适用'),
                ],
                default='not_applicable',
                editable=False,
                max_length=32,
                verbose_name='密码恢复状态',
            ),
        ),
        migrations.CreateModel(
            name='PasswordSecurityAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(choices=[('reveal', '查看学生密码'), ('manual_reset', '手工重置密码'), ('generated_reset', '生成临时密码')], max_length=24)),
                ('actor_user_id', models.PositiveBigIntegerField(blank=True, null=True)),
                ('target_user_id', models.PositiveBigIntegerField(blank=True, null=True)),
                ('outcome', models.CharField(choices=[('success', '成功'), ('denied', '拒绝'), ('not_found', '目标不存在'), ('unavailable', '密码不可恢复'), ('rate_limited', '触发限流'), ('error', '安全失败')], max_length=24)),
                ('reason_code', models.CharField(blank=True, max_length=48)),
                ('source_ip', models.GenericIPAddressField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': '密码安全审计',
                'verbose_name_plural': '密码安全审计',
                'ordering': ['-created_at'],
            },
        ),
        migrations.RunPython(encrypt_legacy_passwords, migrations.RunPython.noop),
    ]
