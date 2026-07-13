import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponsePermanentRedirect, JsonResponse

logger = logging.getLogger('django.security')


class PermanentPreserveRedirect(HttpResponsePermanentRedirect):
    status_code = 308


class CanonicalHostRedirectMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response
        self.canonical_host = getattr(settings, 'CANONICAL_HOST', '').lower()
        self.redirect_hosts = {
            host.lower()
            for host in getattr(settings, 'CANONICAL_REDIRECT_HOSTS', [])
            if host
        }

    def __call__(self, request):
        if self.canonical_host and self.redirect_hosts:
            host = request.get_host().split(':', 1)[0].lower()
            if host in self.redirect_hosts:
                return PermanentPreserveRedirect(
                    f'https://{self.canonical_host}{request.get_full_path()}'
                )
        return self.get_response(request)


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


class GlobalRateLimitMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response
        self.max_requests = getattr(settings, 'GLOBAL_RATE_LIMIT_MAX', 60)
        self.window = getattr(settings, 'GLOBAL_RATE_LIMIT_WINDOW', 60)

    def __call__(self, request):
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            return self.get_response(request)

        ip = LoginRateLimitMiddleware._client_ip(request)
        cache_key = f'global_rl:{ip}'
        hits = cache.get(cache_key, 0)

        if hits >= self.max_requests:
            logger.warning('Global rate limit exceeded for IP %s (%d reqs)', ip, hits)
            return JsonResponse(
                {'error': 'Muitas requisições. Aguarde um momento.'},
                status=429,
            )

        cache.set(cache_key, hits + 1, self.window)
        return self.get_response(request)


class VercelCDNCacheMiddleware:
    """Add s-maxage + stale-while-revalidate so Vercel CDN caches public pages."""

    SKIP_PREFIXES = ('/painel/', '/admin/', '/conta/', '/checkout/', '/pagamento/', '/carrinho/')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.method != 'GET' or response.status_code != 200:
            return response
        if any(request.path.startswith(p) for p in self.SKIP_PREFIXES):
            return response
        if hasattr(request, 'user') and request.user.is_authenticated:
            return response
        if request.COOKIES.get('sessionid'):
            return response
        if response.get('Content-Type', '').startswith('application/json'):
            return response

        response['Cache-Control'] = 'public, s-maxage=60, stale-while-revalidate=300'
        if response.has_header('Vary'):
            del response['Vary']
        response.cookies.clear()
        if response.has_header('Set-Cookie'):
            del response['Set-Cookie']
        return response
