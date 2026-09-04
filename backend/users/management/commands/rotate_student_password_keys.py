from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from users.models import CustomUser
from users.security import PasswordEncryptionError, StudentPasswordCipher


class Command(BaseCommand):
    help = '校验或轮换学生可恢复密码到当前 primary key（不输出密码材料）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='实际写入；省略时只执行解密与哈希校验',
        )

    def handle(self, *args, **options):
        apply_changes = options['apply']
        cipher = StudentPasswordCipher(settings.STUDENT_PASSWORD_KEY_CONFIG)
        primary_key_id = settings.STUDENT_PASSWORD_KEY_CONFIG.primary_key_id
        checked = 0
        rotated = 0
        try:
            with transaction.atomic():
                users = CustomUser.objects.select_for_update().filter(
                    role='student', password_recovery_status='available'
                ).order_by('pk')
                for user in users.iterator():
                    plaintext = cipher.decrypt(
                        user.encrypted_password, user.password_encryption_key_id
                    )
                    checked += 1
                    if not user.check_password(plaintext):
                        raise CommandError('发现密码哈希与密文不一致，轮换已停止。')
                    if user.password_encryption_key_id != primary_key_id:
                        ciphertext, key_id = cipher.encrypt(plaintext)
                        if apply_changes:
                            user.encrypted_password = ciphertext
                            user.password_encryption_key_id = key_id
                            user.save(update_fields=[
                                'encrypted_password', 'password_encryption_key_id'
                            ])
                        rotated += 1
                    del plaintext
                if not apply_changes:
                    transaction.set_rollback(True)
        except PasswordEncryptionError as exc:
            raise CommandError('学生密码密钥轮换校验失败。') from exc

        mode = '已应用' if apply_changes else '预演'
        self.stdout.write(self.style.SUCCESS(f'学生密码密钥轮换{mode}完成'))
        self.stdout.write(f'已校验：{checked}')
        self.stdout.write(f'需轮换或已轮换：{rotated}')
