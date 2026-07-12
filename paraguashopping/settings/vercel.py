import os
import shutil
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from .base import *


DEBUG = False

SECRET_KEY = config(
    'SECRET_KEY',
    default='django-insecure-vercel-preview-only-change-before-production-essencek',
)

_vercel_url = os.environ.get('VERCEL_URL', '')
SITE_URL = config('SITE_URL', default='https://essencekimportados.com.br')

ALLOWED_HOSTS = [
    '.vercel.app',
    'essencekimportado.com',
    'www.essencekimportado.com',
    'essencekimportados.com.br',
    'www.essencekimportados.com.br',
    'localhost',
    '127.0.0.1',
]
if _vercel_url:
    ALLOWED_HOSTS.append(_vercel_url)

CSRF_TRUSTED_ORIGINS = [
    'https://*.vercel.app',
    'https://essencekimportado.com',
    'https://www.essencekimportado.com',
    'https://essencekimportados.com.br',
    'https://www.essencekimportados.com.br',
]
if _vercel_url:
    CSRF_TRUSTED_ORIGINS.append(f'https://{_vercel_url}')

CANONICAL_HOST = 'essencekimportados.com.br'
CANONICAL_REDIRECT_HOSTS = [
    'www.essencekimportados.com.br',
    'essencekimportado.com',
    'www.essencekimportado.com',
]
MIDDLEWARE = ['core.middleware.CanonicalHostRedirectMiddleware', *MIDDLEWARE]

_database_url = config('DATABASE_URL', default='') or config('POSTGRES_URL', default='')
_is_vercel_environment = bool(os.environ.get('VERCEL') or os.environ.get('VERCEL_ENV') or _vercel_url)

if _database_url:
    DATABASES = {
        'default': dj_database_url.parse(
            _database_url,
            conn_max_age=600,
            ssl_require=True,
        )
    }
    DATA_PERSISTENCE_MODE = 'persistent'
else:
    _allow_ephemeral_sqlite = config(
        'ALLOW_EPHEMERAL_SQLITE_ON_VERCEL',
        default=not _is_vercel_environment,
        cast=bool,
    )
    if not _allow_ephemeral_sqlite:
        raise ImproperlyConfigured(
            'Configure DATABASE_URL ou POSTGRES_URL com um banco persistente para a Vercel. '
            'SQLite em /tmp apaga cadastros de produtos, marcas, categorias e pedidos em cold starts/redeploys.'
        )

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
    DATA_PERSISTENCE_MODE = 'ephemeral-sqlite'

_preview_runtime_media = Path(config('VERCEL_PREVIEW_RUNTIME_MEDIA', default='/tmp/essencek_media'))
_preview_runtime_media.mkdir(parents=True, exist_ok=True)

MEDIA_ROOT = _preview_runtime_media
SERVE_MEDIA_FILES = True
USE_DATABASE_MEDIA_STORAGE_ON_VERCEL = config(
    'USE_DATABASE_MEDIA_STORAGE_ON_VERCEL',
    default=bool(_database_url),
    cast=bool,
)

if USE_DATABASE_MEDIA_STORAGE_ON_VERCEL:
    DEFAULT_FILE_STORAGE = 'core.storage.PersistentMediaStorage'

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

COSMOS_API_TOKEN = config('COSMOS_API_TOKEN', default='')

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
