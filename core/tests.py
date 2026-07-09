from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from .middleware import CanonicalHostRedirectMiddleware


class CanonicalHostRedirectMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _response(self, request):
        return HttpResponse('ok')

    @override_settings(
        ALLOWED_HOSTS=['essencekimportados.com.br', 'www.essencekimportados.com.br'],
        CANONICAL_HOST='essencekimportados.com.br',
        CANONICAL_REDIRECT_HOSTS=['www.essencekimportados.com.br'],
    )
    def test_redirects_www_to_canonical_host(self):
        middleware = CanonicalHostRedirectMiddleware(self._response)
        request = self.factory.get(
            '/painel/marcas/?page=1',
            HTTP_HOST='www.essencekimportados.com.br',
            secure=True,
        )

        response = middleware(request)

        self.assertEqual(response.status_code, 308)
        self.assertEqual(
            response['Location'],
            'https://essencekimportados.com.br/painel/marcas/?page=1',
        )

    @override_settings(
        ALLOWED_HOSTS=['essencekimportados.com.br', 'www.essencekimportados.com.br'],
        CANONICAL_HOST='essencekimportados.com.br',
        CANONICAL_REDIRECT_HOSTS=['www.essencekimportados.com.br'],
    )
    def test_allows_canonical_host_without_redirect(self):
        middleware = CanonicalHostRedirectMiddleware(self._response)
        request = self.factory.get(
            '/',
            HTTP_HOST='essencekimportados.com.br',
            secure=True,
        )

        response = middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'ok')
