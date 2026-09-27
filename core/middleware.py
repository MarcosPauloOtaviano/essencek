import logging
import ipaddress
from django.conf import settings
from django.http import HttpResponsePermanentRedirect, JsonResponse
from django.utils.cache import patch_vary_headers

from .rate_limit import hit as rate_limit_hit, reset as rate_limit_reset

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
        policy = getattr(settings, 'CONTENT_SECURITY_POLICY', '')
        if policy:
            response['Content-Security-Policy'] = policy
        if request.is_secure():
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
        return response


class LoginRateLimitMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response
        self.max_attempts = getattr(settings, 'LOGIN_RATE_LIMIT_MAX_ATTEMPTS', 5)
        self.window = getattr(settings, 'LOGIN_RATE_LIMIT_WINDOW_SECONDS', 300)

    def __call__(self, request):
        login_path = request.path in ('/conta/entrar/', '/admin/login/') or (
            request.path.startswith('/conta/2fa/') and request.path.endswith('/login/')
        )
        if request.method == 'POST' and login_path:
            ip = self._client_ip(request)
            blocked, attempts, retry_after = rate_limit_hit(
                'login', ip, self.max_attempts, self.window
            )
            if blocked:
                logger.warning('Login rate limit exceeded')
                response = JsonResponse(
                    {'error': 'Muitas tentativas de login. Aguarde alguns minutos.'},
                    status=429,
                )
                response['Retry-After'] = str(retry_after)
                return response

            response = self.get_response(request)

            if hasattr(request, 'user') and request.user.is_authenticated:
                rate_limit_reset('login', ip)

            return response

        return self.get_response(request)

    @staticmethod
    def _client_ip(request):
        candidate = request.META.get('REMOTE_ADDR', '')
        if getattr(settings, 'TRUST_VERCEL_PROXY', False):
            candidate = request.META.get('HTTP_X_VERCEL_FORWARDED_FOR') or candidate
        candidate = candidate.split(',')[0].strip()
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            return 'unknown'


class GlobalRateLimitMiddleware:

    EXEMPT_PREFIXES = (
        '/static/', '/media/', '/health/', '/cron/', '/pagamento/webhook/',
    )

    def __init__(self, get_response):
        self.get_response = get_response
        self.max_requests = getattr(settings, 'GLOBAL_RATE_LIMIT_MAX', 60)
        self.window = getattr(settings, 'GLOBAL_RATE_LIMIT_WINDOW', 60)

    def __call__(self, request):
        if request.method == 'OPTIONS' or any(
            request.path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES
        ):
            return self.get_response(request)

        ip = LoginRateLimitMiddleware._client_ip(request)
        blocked, hits, retry_after = rate_limit_hit(
            'global', ip, self.max_requests, self.window
        )
        if blocked:
            logger.warning('Global rate limit exceeded (%d reqs)', hits)
            response = JsonResponse(
                {'error': 'Muitas requisições. Aguarde um momento.'},
                status=429,
            )
            response['Retry-After'] = str(retry_after)
            return response

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
        if response.cookies or response.has_header('Set-Cookie'):
            return response
        if getattr(response, 'streaming', False):
            return response
        if b'csrfmiddlewaretoken' in response.content:
            return response

        patch_vary_headers(response, ('Cookie',))
        response['Cache-Control'] = 'public, s-maxage=60, stale-while-revalidate=300'
        return response
