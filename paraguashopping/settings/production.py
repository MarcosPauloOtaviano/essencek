from .base import *
from decouple import config
from django.core.exceptions import ImproperlyConfigured


def csv_config(name, default=''):
    return [value.strip() for value in config(name, default=default).split(',') if value.strip()]

DEBUG = False
ALLOWED_HOSTS = csv_config('ALLOWED_HOSTS')
CSRF_TRUSTED_ORIGINS = csv_config('CSRF_TRUSTED_ORIGINS')

if not ALLOWED_HOSTS:
    raise ImproperlyConfigured('Defina ALLOWED_HOSTS no ambiente de produção.')

if SECRET_KEY.startswith('django-insecure') or len(SECRET_KEY) < 50:
    raise ImproperlyConfigured('Defina uma SECRET_KEY forte no ambiente de produção.')

if not SITE_URL or SITE_URL.startswith('http://127.0.0.1') or SITE_URL.startswith('http://localhost'):
    raise ImproperlyConfigured('Defina SITE_URL com o domínio público HTTPS da loja em produção.')

DB_ENGINE = config('DB_ENGINE', default='django.db.backends.postgresql')

if DB_ENGINE == 'django.db.backends.sqlite3':
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': config('DB_NAME'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': config('DB_NAME'),
            'USER': config('DB_USER'),
            'PASSWORD': config('DB_PASSWORD'),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='3306'),
        }
    }

# Security — TLS / HTTPS / HSTS
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
if config('USE_X_FORWARDED_PROTO', default=True, cast=bool):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Fernet encryption key for AES (must be 32-byte url-safe base64)
FERNET_KEYS = [config('FERNET_KEY')]

# Session hardening
SESSION_COOKIE_AGE = 3600 * 8  # 8 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')

# Payment production
PAYMENT_SANDBOX = config('PAYMENT_SANDBOX', default=False, cast=bool)
PAYMENT_GATEWAY = config('PAYMENT_GATEWAY', default='mercadopago')
MP_ACCESS_TOKEN = config('MP_ACCESS_TOKEN', default='')
MP_PUBLIC_KEY = config('MP_PUBLIC_KEY', default='')
MP_WEBHOOK_SECRET = config('MP_WEBHOOK_SECRET', default='')
MP_USE_SANDBOX_LINK = config('MP_USE_SANDBOX_LINK', default=False, cast=bool)
MP_MAX_INSTALLMENTS = config('MP_MAX_INSTALLMENTS', default=12, cast=int)

# Shipping production
MELHORENVIO_TOKEN = config('MELHORENVIO_TOKEN', default='')
MELHORENVIO_ENV = 'production'
