"""Student recoverable-password encryption configuration and primitives."""

import re
from dataclasses import dataclass
from types import MappingProxyType

from cryptography.fernet import Fernet, InvalidToken
from django.core.exceptions import ImproperlyConfigured


KEY_ID_PATTERN = re.compile(r'^[A-Za-z0-9._-]{1,40}$')


class PasswordEncryptionError(Exception):
    """Safe domain error that never includes key or password material."""


@dataclass(frozen=True)
class PasswordKeyConfig:
    keys: object
    primary_key_id: str

    @property
    def configured(self):
        return bool(self.keys) and self.primary_key_id in self.keys


def parse_password_key_config(raw_keys, primary_key_id):
    raw_keys = (raw_keys or '').strip()
    primary_key_id = (primary_key_id or '').strip()
    if not raw_keys and not primary_key_id:
        return PasswordKeyConfig(MappingProxyType({}), '')
    if not raw_keys or not primary_key_id:
        raise ImproperlyConfigured(
            '学生密码加密密钥和主密钥 ID 必须同时配置。'
        )

    keys = {}
    for item in raw_keys.split(','):
        item = item.strip()
        if not item or ':' not in item:
            raise ImproperlyConfigured('学生密码加密密钥列表格式无效。')
        key_id, encoded_key = item.split(':', 1)
        key_id = key_id.strip()
        encoded_key = encoded_key.strip()
        if not KEY_ID_PATTERN.fullmatch(key_id):
            raise ImproperlyConfigured('学生密码加密 key ID 格式无效。')
        if key_id in keys:
            raise ImproperlyConfigured('学生密码加密 key ID 不能重复。')
        try:
            Fernet(encoded_key.encode('ascii'))
        except (TypeError, ValueError, UnicodeEncodeError) as exc:
            raise ImproperlyConfigured('学生密码加密 key 格式无效。') from exc
        keys[key_id] = encoded_key

    if primary_key_id not in keys:
        raise ImproperlyConfigured('学生密码加密主 key ID 不在密钥列表中。')
    return PasswordKeyConfig(MappingProxyType(keys), primary_key_id)


class StudentPasswordCipher:
    def __init__(self, config):
        if not config.configured:
            raise PasswordEncryptionError('学生密码加密服务未配置。')
        self._config = config

    def encrypt(self, plaintext):
        if not isinstance(plaintext, str) or not plaintext:
            raise PasswordEncryptionError('学生密码内容无效。')
        key_id = self._config.primary_key_id
        fernet = Fernet(self._config.keys[key_id].encode('ascii'))
        ciphertext = fernet.encrypt(plaintext.encode('utf-8')).decode('ascii')
        return ciphertext, key_id

    def decrypt(self, ciphertext, key_id):
        if not ciphertext or key_id not in self._config.keys:
            raise PasswordEncryptionError('学生密码暂时无法解密。')
        try:
            plaintext = Fernet(
                self._config.keys[key_id].encode('ascii')
            ).decrypt(ciphertext.encode('ascii')).decode('utf-8')
        except (InvalidToken, UnicodeError, ValueError, TypeError) as exc:
            raise PasswordEncryptionError('学生密码暂时无法解密。') from exc
        if not plaintext:
            raise PasswordEncryptionError('学生密码暂时无法解密。')
        return plaintext
