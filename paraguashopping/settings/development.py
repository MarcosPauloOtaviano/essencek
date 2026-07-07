from .base import *

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0', '.trycloudflare.com']
CSRF_TRUSTED_ORIGINS = ['https://*.trycloudflare.com']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Development email backend
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Payment sandbox mode
PAYMENT_SANDBOX = config('PAYMENT_SANDBOX', default=True, cast=bool)
PAYMENT_GATEWAY = config('PAYMENT_GATEWAY', default='sandbox')
MP_ACCESS_TOKEN = config('MP_ACCESS_TOKEN', default='')
MP_PUBLIC_KEY = config('MP_PUBLIC_KEY', default='')
MP_WEBHOOK_SECRET = config('MP_WEBHOOK_SECRET', default='')
MP_USE_SANDBOX_LINK = config('MP_USE_SANDBOX_LINK', default=True, cast=bool)
MP_MAX_INSTALLMENTS = config('MP_MAX_INSTALLMENTS', default=12, cast=int)

# Shipping sandbox
MELHORENVIO_TOKEN = config('MELHORENVIO_TOKEN', default='')
MELHORENVIO_ENV = 'sandbox'
