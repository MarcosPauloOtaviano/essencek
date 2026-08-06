from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from .development import *


_e2e_db_value = config('ESSENCEK_E2E_DB_PATH', default='').strip()
if not _e2e_db_value:
    raise ImproperlyConfigured('Defina ESSENCEK_E2E_DB_PATH para uma cópia isolada do banco.')

_e2e_db_path = Path(_e2e_db_value).expanduser().resolve()
_protected_databases = {
    (BASE_DIR / 'db.sqlite3').resolve(),
    (BASE_DIR / 'vercel_db.sqlite3').resolve(),
}
if _e2e_db_path in _protected_databases:
    raise ImproperlyConfigured('O teste E2E não pode usar um banco SQLite principal do projeto.')

_e2e_db_path.parent.mkdir(parents=True, exist_ok=True)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': str(_e2e_db_path),
    }
}

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
DEBUG = config('ESSENCEK_E2E_DEBUG', default=True, cast=bool)
