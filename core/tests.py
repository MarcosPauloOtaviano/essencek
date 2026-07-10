from types import SimpleNamespace
from unittest.mock import patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse

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


class ExchangeRateCronTests(SimpleTestCase):
    @override_settings(CRON_SECRET='cron-test-secret')
    def test_cron_rejects_missing_authorization(self):
        response = self.client.get(reverse('cron_update_exchange_rates'))

        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.json()['ok'])

    @override_settings(CRON_SECRET='cron-test-secret')
    @patch('core.views.update_all_exchange_rates_from_api')
    def test_cron_updates_exchange_rates_with_authorization(self, update_mock):
        update_mock.return_value = [
            SimpleNamespace(
                currency_from='USD',
                currency_to='BRL',
                rate='5.4321',
                source='teste',
                updated_at=SimpleNamespace(isoformat=lambda: '2026-07-10T09:00:00+00:00'),
            )
        ]

        response = self.client.get(
            reverse('cron_update_exchange_rates'),
            HTTP_AUTHORIZATION='Bearer cron-test-secret',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['updated'][0]['pair'], 'USD-BRL')
        update_mock.assert_called_once_with()
