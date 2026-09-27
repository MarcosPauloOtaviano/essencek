import base64
import hashlib
from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')
SECRET_KEY_FALLBACKS = [
    key.strip()
    for key in config('SECRET_KEY_FALLBACKS', default='').split(',')
    if key.strip()
]
SITE_URL = config('SITE_URL', default='http://127.0.0.1:8000')
STORE_WHATSAPP = config(
    'STORE_WHATSAPP',
    default=config('STORE_PHONE', default='5535999073391'),
)
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    # Third party
    'crispy_forms',
    'crispy_bootstrap5',
    'widget_tweaks',
    # Security / MFA
    'django_otp',
    'django_otp.plugins.otp_totp',
    'django_otp.plugins.otp_static',
    'two_factor',
    'two_factor.plugins.phonenumber',
    # Local
    'core',
    'accounts',
    'products',
    'cart',
    'orders',
    'payments',
    'shipping',
    'dashboard',
    'reports',
]

MIDDLEWARE = [
    'core.middleware.VercelCDNCacheMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.SecurityHeadersMiddleware',
    'core.middleware.LoginRateLimitMiddleware',
    'core.middleware.GlobalRateLimitMiddleware',
]

ROOT_URLCONF = 'paraguashopping.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.store_settings',
                'core.context_processors.exchange_rate',
                'core.context_processors.site_navigation',
                'cart.context_processors.cart_count',
            ],
        },
    },
]

WSGI_APPLICATION = 'paraguashopping.wsgi.application'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = Path(config('STATIC_ROOT', default=str(BASE_DIR / 'staticfiles')))
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = Path(config('MEDIA_ROOT', default=str(BASE_DIR / 'media')))

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'accounts.User'

LOGIN_URL = '/conta/entrar/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_REFERRER_POLICY = 'same-origin'

# Session hardening
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 3600 * 12  # 12 hours

# Brute-force mitigation: max login attempts
LOGIN_RATE_LIMIT_MAX_ATTEMPTS = 5
LOGIN_RATE_LIMIT_WINDOW_SECONDS = 300

CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

# File upload security
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp', 'heic', 'heif']

# Exchange rate
EXCHANGE_RATE_API_URL = config('EXCHANGE_RATE_API_URL', default='https://economia.awesomeapi.com.br/json/last/USD-BRL')
EXCHANGE_RATE_API_BASE_URL = config('EXCHANGE_RATE_API_BASE_URL', default='https://economia.awesomeapi.com.br/json/last/{pairs}')
EXCHANGE_RATE_FALLBACK_API_URL = config('EXCHANGE_RATE_FALLBACK_API_URL', default='https://open.er-api.com/v6/latest/{base}')
EXCHANGE_RATE_CACHE_SECONDS = config('EXCHANGE_RATE_CACHE_SECONDS', default=3600, cast=int)
EXCHANGE_RATE_DEFAULT_USD_BRL = config('EXCHANGE_RATE_DEFAULT_USD_BRL', default='5.50')
EXCHANGE_RATE_PAIRS = [
    pair.strip().upper()
    for pair in config('EXCHANGE_RATE_PAIRS', default='USD-BRL').split(',')
    if pair.strip()
]
CRON_SECRET = config('CRON_SECRET', default='')

# GTIN / barcode catalog lookup
COSMOS_API_TOKEN = config('COSMOS_API_TOKEN', default='')

# Frenet shipping API
FRENET_TOKEN = config('FRENET_TOKEN', default='')
FRENET_SENDER_CEP = config('FRENET_SENDER_CEP', default='85851130')

# Fernet encryption for sensitive fields. Production always supplies an
# independent key; the derived value is only a valid local-development fallback.
_default_fernet_key = base64.urlsafe_b64encode(
    hashlib.sha256(SECRET_KEY.encode('utf-8')).digest()
).decode('ascii')
FERNET_KEYS = [config('FERNET_KEY', default=_default_fernet_key)]
PII_HASH_KEY = config('PII_HASH_KEY', default=SECRET_KEY)

# Mercado Pago
PAYMENT_GATEWAY = config('PAYMENT_GATEWAY', default='sandbox')
PAYMENT_SANDBOX = config('PAYMENT_SANDBOX', default='True', cast=bool)
MP_ACCESS_TOKEN = config('MP_ACCESS_TOKEN', default='')
MP_PUBLIC_KEY = config('MP_PUBLIC_KEY', default='')
MP_WEBHOOK_SECRET = config('MP_WEBHOOK_SECRET', default='')
MP_WEBHOOK_TOKEN = config('MP_WEBHOOK_TOKEN', default='')
MP_USE_SANDBOX_LINK = config('MP_USE_SANDBOX_LINK', default='True', cast=bool)
MP_MAX_INSTALLMENTS = config('MP_MAX_INSTALLMENTS', default=12, cast=int)

# Two-factor auth (protects /painel/ admin area)
TWO_FACTOR_REMEMBER_COOKIE_AGE = 30 * 24 * 3600
TWO_FACTOR_LOGIN_TIMEOUT = 600

# Shared throttling is enabled by production settings. Development and tests
# keep the local cache backend to avoid coupling routine work to PostgreSQL.
SHARED_RATE_LIMIT_ENABLED = False
GLOBAL_RATE_LIMIT_MAX = config('GLOBAL_RATE_LIMIT_MAX', default=240, cast=int)
GLOBAL_RATE_LIMIT_WINDOW = config('GLOBAL_RATE_LIMIT_WINDOW', default=60, cast=int)

# Enforcing CSP kept compatible with the current inline template handlers.
# The remote origins are restricted to services used by the storefront.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "object-src 'none'; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
    "font-src 'self' data: https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
    "img-src 'self' data: blob: https:; "
    "connect-src 'self' https://viacep.com.br; "
    "media-src 'self' blob:; "
    "worker-src 'self' blob:; "
    "upgrade-insecure-requests"
)

# Store settings cache key
STORE_SETTINGS_CACHE_KEY = 'store_settings'

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'products.gtin': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# Error monitoring is enabled only when a DSN is configured. Sensitive request
# data is never sent by default.
SENTRY_DSN = config('SENTRY_DSN', default='').strip()
if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=config('SENTRY_ENVIRONMENT', default='development'),
        release=config('VERCEL_GIT_COMMIT_SHA', default='') or None,
        send_default_pii=False,
        traces_sample_rate=config('SENTRY_TRACES_SAMPLE_RATE', default=0.05, cast=float),
    )
