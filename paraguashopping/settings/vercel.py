import os
import shutil
from pathlib import Path

from .base import *


DEBUG = False

SECRET_KEY = config(
    'SECRET_KEY',
    default='django-insecure-vercel-preview-only-change-before-production-essencek',
)

_vercel_url = os.environ.get('VERCEL_URL', '')
SITE_URL = config('SITE_URL', default='https://essencekimportado.com')

ALLOWED_HOSTS = [
    '.vercel.app',
    'essencekimportado.com',
    'www.essencekimportado.com',
    'localhost',
    '127.0.0.1',
]
if _vercel_url:
    ALLOWED_HOSTS.append(_vercel_url)

CSRF_TRUSTED_ORIGINS = [
    'https://*.vercel.app',
    'https://essencekimportado.com',
    'https://www.essencekimportado.com',
]
if _vercel_url:
    CSRF_TRUSTED_ORIGINS.append(f'https://{_vercel_url}')

_preview_source_db = Path(config('VERCEL_PREVIEW_SOURCE_DB', default=str(BASE_DIR / 'vercel_db.sqlite3')))
_preview_runtime_db = Path(config('VERCEL_PREVIEW_RUNTIME_DB', default='/tmp/essencek_preview.sqlite3'))
if _preview_source_db.exists() and not _preview_runtime_db.exists():
    _preview_runtime_db.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_preview_source_db, _preview_runtime_db)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': str(_preview_runtime_db),
    }
}

_preview_source_media = BASE_DIR / 'media'
_preview_runtime_media = Path(config('VERCEL_PREVIEW_RUNTIME_MEDIA', default='/tmp/essencek_media'))
if _preview_source_media.exists():
    _preview_runtime_media.mkdir(parents=True, exist_ok=True)
    for source_path in _preview_source_media.rglob('*'):
        if not source_path.is_file():
            continue
        target_path = _preview_runtime_media / source_path.relative_to(_preview_source_media)
        if target_path.exists():
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(source_path, target_path)
        except OSError:
            pass

MEDIA_ROOT = _preview_runtime_media
SERVE_MEDIA_FILES = True

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

PAYMENT_SANDBOX = True
PAYMENT_GATEWAY = config('PAYMENT_GATEWAY', default='sandbox')
MP_ACCESS_TOKEN = ''
MP_PUBLIC_KEY = ''
MP_WEBHOOK_SECRET = ''
MP_USE_SANDBOX_LINK = True
MP_MAX_INSTALLMENTS = config('MP_MAX_INSTALLMENTS', default=12, cast=int)

SECURE_SSL_REDIRECT = False

SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

FERNET_KEYS = [
    config('FERNET_KEY', default='YWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWE='),
]
