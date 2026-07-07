import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse

logger = logging.getLogger('django.security')


class SecurityHeadersMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = (
            'camera=(self), microphone=(), geolocation=(), payment=()'
        )
        response['Cross-Origin-Opener-Policy'] = 'same-origin'
        response['Cross-Origin-Resource-Policy'] = 'same-origin'
        if request.is_secure():
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
        return response


class LoginRateLimitMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response
        self.max_attempts = getattr(settings, 'LOGIN_RATE_LIMIT_MAX_ATTEMPTS', 5)
        self.window = getattr(settings, 'LOGIN_RATE_LIMIT_WINDOW_SECONDS', 300)

    def __call__(self, request):
        if request.method == 'POST' and request.path in ('/conta/entrar/', '/admin/login/'):
            ip = self._client_ip(request)
            cache_key = f'login_attempts:{ip}'
            attempts = cache.get(cache_key, [])
            now = time.time()
            attempts = [t for t in attempts if now - t < self.window]

            if len(attempts) >= self.max_attempts:
                logger.warning('Login rate limit exceeded for IP %s', ip)
                return JsonResponse(
                    {'error': 'Muitas tentativas de login. Aguarde alguns minutos.'},
                    status=429,
                )

            response = self.get_response(request)

            if response.status_code == 200 and not getattr(request, 'user', None) or (
                hasattr(request, 'user') and not request.user.is_authenticated
            ):
                attempts.append(now)
                cache.set(cache_key, attempts, self.window)

            return response

        return self.get_response(request)

    @staticmethod
    def _client_ip(request):
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')
