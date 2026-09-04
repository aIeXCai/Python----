from django.db import migrations, models
from django.db.models import Q


def verify_encrypted_passwords(apps, schema_editor):
    User = apps.get_model('users', 'CustomUser')
    invalid_available = User.objects.filter(password_recovery_status='available').filter(
        Q(encrypted_password__isnull=True)
        | Q(encrypted_password='')
        | Q(password_encryption_key_id__isnull=True)
        | Q(password_encryption_key_id='')
        | ~Q(role='student')
    )
    if invalid_available.exists():
        raise RuntimeError('学生密码密文核验失败，拒绝删除历史明文字段。')


class Migration(migrations.Migration):
    atomic = True

    dependencies = [
        ('users', '0006_add_encrypted_password_and_audit'),
    ]

    operations = [
        migrations.RunPython(verify_encrypted_passwords, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='customuser',
            name='plain_password',
        ),
        migrations.AddConstraint(
            model_name='customuser',
            constraint=models.CheckConstraint(
                condition=(
                    ~Q(password_recovery_status='available')
                    | (
                        Q(role='student')
                        & Q(encrypted_password__isnull=False)
                        & ~Q(encrypted_password='')
                        & Q(password_encryption_key_id__isnull=False)
                        & ~Q(password_encryption_key_id='')
                    )
                ),
                name='users_available_password_has_ciphertext',
            ),
        ),
        migrations.AddIndex(
            model_name='passwordsecurityaudit',
            index=models.Index(fields=['actor_user_id', 'event_type', 'created_at'], name='pwd_audit_actor_event_time'),
        ),
        migrations.AddIndex(
            model_name='passwordsecurityaudit',
            index=models.Index(fields=['target_user_id', 'created_at'], name='pwd_audit_target_time'),
        ),
        migrations.AddIndex(
            model_name='passwordsecurityaudit',
            index=models.Index(fields=['outcome', 'created_at'], name='pwd_audit_outcome_time'),
        ),
    ]
