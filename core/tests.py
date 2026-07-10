from types import SimpleNamespace
from unittest.mock import patch

import requests
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse

from .middleware import CanonicalHostRedirectMiddleware
from .services import fetch_exchange_rates


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


class ExchangeRateServiceTests(SimpleTestCase):
    @override_settings(
        EXCHANGE_RATE_API_URL='https://primary.example/USD-BRL',
        EXCHANGE_RATE_FALLBACK_API_URL='https://fallback.example/{base}',
    )
    @patch('core.services.requests.get')
    def test_fetch_exchange_rates_uses_fallback_when_primary_is_limited(self, get_mock):
        primary_response = SimpleNamespace(
            raise_for_status=lambda: (_ for _ in ()).throw(requests.HTTPError('429')),
            json=lambda: {},
        )
        fallback_response = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                'provider': 'fallback',
                'time_last_update_utc': 'today',
                'rates': {'BRL': 5.12},
            },
        )
        get_mock.side_effect = [primary_response, fallback_response]

        rates = fetch_exchange_rates(['USD-BRL'])

        self.assertEqual(str(rates[('USD', 'BRL')][0]), '5.1200')
        self.assertIn('fallback', rates[('USD', 'BRL')][1])
