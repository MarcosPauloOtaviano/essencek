from types import SimpleNamespace
from unittest.mock import patch

import requests
from django.http import HttpResponse
from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse
from django.views.defaults import server_error

from .middleware import (
    CanonicalHostRedirectMiddleware,
    LoginRateLimitMiddleware,
    VercelCDNCacheMiddleware,
)
from .media_views import _clean_media_path
from .services import fetch_exchange_rates, get_store_whatsapp_url
from .storage import PersistentMediaStorage
from .utils import image_url_if_exists


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


class VercelCDNCacheMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_adds_public_cache_headers_for_plain_anonymous_pages(self):
        middleware = VercelCDNCacheMiddleware(lambda request: HttpResponse('ok'))
        request = self.factory.get('/sobre/')

        response = middleware(request)

        self.assertEqual(response['Cache-Control'], 'public, s-maxage=60, stale-while-revalidate=300')
        self.assertIn('Cookie', response['Vary'])

    def test_does_not_cache_pages_that_need_csrf_cookie(self):
        response = HttpResponse('<input type="hidden" name="csrfmiddlewaretoken" value="abc">')
        response.set_cookie('csrftoken', 'abc')
        middleware = VercelCDNCacheMiddleware(lambda request: response)
        request = self.factory.get('/')

        result = middleware(request)

        self.assertFalse(result.has_header('Cache-Control'))
        self.assertIn('csrftoken', result.cookies)


class LoginRateLimitMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def tearDown(self):
        from django.core.cache import cache

        cache.clear()

    def test_successful_login_clears_previous_failures(self):
        from django.core.cache import cache

        cache_key = 'login_attempts:127.0.0.1'
        cache.set(cache_key, [1.0], 300)

        def successful_login(request):
            request.user = SimpleNamespace(is_authenticated=True)
            return HttpResponse(status=302)

        middleware = LoginRateLimitMiddleware(successful_login)
        request = self.factory.post('/conta/entrar/')

        middleware(request)

        self.assertIsNone(cache.get(cache_key))


class ImageUrlIfExistsTests(SimpleTestCase):
    def test_persistent_media_storage_returns_url_without_exists_lookup(self):
        class PersistentMediaStorage:
            def exists(self, name):
                raise AssertionError('exists should not be called for persistent media')

        class FakeImageField:
            name = 'products/foto.jpg'
            storage = PersistentMediaStorage()

            @property
            def url(self):
                return '/media/products/foto.jpg'

        self.assertEqual(image_url_if_exists(FakeImageField()), '/media/products/foto.jpg')


class StoreContactTests(SimpleTestCase):
    def test_store_whatsapp_url_is_normalized_from_central_setting(self):
        store = SimpleNamespace(whatsapp='(35) 99907-3391')

        self.assertEqual(get_store_whatsapp_url(store), 'https://wa.me/5535999073391')


class ErrorPageTests(SimpleTestCase):
    @override_settings(DEBUG=False)
    def test_not_found_page_uses_store_layout(self):
        response = self.client.get('/pagina-que-nao-existe/')

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'Página não encontrada', status_code=404)
        self.assertContains(response, 'Voltar para a loja', status_code=404)

    @override_settings(DEBUG=False)
    def test_server_error_page_explains_that_order_is_not_complete(self):
        response = server_error(RequestFactory().get('/falha/'))

        self.assertEqual(response.status_code, 500)
        self.assertContains(response, 'Não foi possível concluir agora', status_code=500)
        self.assertContains(response, 'Nenhum pedido é considerado concluído', status_code=500)


class MediaPathSecurityTests(SimpleTestCase):
    def test_media_view_rejects_parent_directory_segments(self):
        with self.assertRaises(Http404):
            _clean_media_path('../.env')

    def test_persistent_storage_rejects_parent_directory_segments(self):
        storage = PersistentMediaStorage(location='C:/paragua/media', base_url='/media/')

        with self.assertRaises(ValueError):
            storage._clean_name('products/../../.env')


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
