import base64

from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings
from django.db import models


def _get_fernet():
    keys = getattr(settings, 'FERNET_KEYS', [settings.SECRET_KEY[:43] + '='])
    fernets = []
    for key in keys:
        key_bytes = key.encode() if isinstance(key, str) else key
        if len(key_bytes) == 32:
            key_bytes = base64.urlsafe_b64encode(key_bytes)
        fernets.append(Fernet(key_bytes))
    return MultiFernet(fernets)


def encrypt_value(plaintext):
    if not plaintext:
        return ''
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext):
    if not ciphertext:
        return ''
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()


class EncryptedCharField(models.TextField):
    """Stores data encrypted at rest using Fernet (AES-128-CBC with HMAC)."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('blank', True)
        kwargs.setdefault('default', '')
        super().__init__(*args, **kwargs)

    def get_prep_value(self, value):
        if value is None or value == '':
            return ''
        return encrypt_value(str(value))

    def from_db_value(self, value, expression, connection):
        if not value:
            return ''
        try:
            return decrypt_value(value)
        except Exception:
            return value

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs.pop('blank', None)
        kwargs.pop('default', None)
        return name, 'core.encryption.EncryptedCharField', args, kwargs
