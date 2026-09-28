import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch

from cryptography.fernet import InvalidToken
from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.core.cache import cache
from django.db import connection, connections, close_old_connections
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, SimpleTestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.forms import ProfileForm
from accounts.models import User
from core.encryption import decrypt_value, EncryptedCharField
from core.middleware import GlobalRateLimitMiddleware, LoginRateLimitMiddleware
from core.models import RateLimitBucket
from core.observability import sanitize_sentry_event
from core.pii import make_pii_lookup
from core.rate_limit import hit
from core.key_rotation import ExpiringFallbackKeys
from orders.models import Order, PreOrderRequest


class IdentitySecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='identity@example.com', email='identity@example.com',
            full_name='Cliente Seguro', cpf='52998224725', whatsapp='11987654321',
            password='StrongTestPass123!',
        )

    def test_profile_keeps_existing_identity_visible(self):
        form = ProfileForm(instance=User.objects.get(pk=self.user.pk))
        self.assertEqual(form['cpf'].value(), '52998224725')
        self.assertEqual(form['whatsapp'].value(), '11987654321')

    def test_partial_identity_update_keeps_blind_index_consistent(self):
        self.user.whatsapp = '21987654321'
        self.user.save(update_fields=['whatsapp_encrypted'])
        self.user.refresh_from_db()
        self.assertEqual(self.user.whatsapp, '21987654321')
        self.assertEqual(self.user.whatsapp_lookup, make_pii_lookup('21987654321'))

    def test_old_version_identity_write_is_readable_until_scrub(self):
        with connection.cursor() as cursor:
            cursor.execute('UPDATE accounts_user SET whatsapp=%s WHERE id=%s', ['21987654321', self.user.pk])
        self.user.refresh_from_db()
        self.assertEqual(self.user.whatsapp, '21987654321')
        self.user.save()
        self.user.refresh_from_db()
        self.assertIsNone(self.user.legacy_whatsapp)
        self.assertEqual(self.user.whatsapp, '21987654321')

    def test_customer_and_admin_name_search_remain_functional(self):
        self.user.is_staff = self.user.is_superuser = True
        self.user.save(update_fields=['is_staff', 'is_superuser'])
        self.client.force_login(self.user)
        for url in ['/painel/clientes/?q=Cliente', '/admin/accounts/user/?q=Cliente']:
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(f'/admin/accounts/user/{self.user.pk}/change/').status_code, 200)

    def test_encrypted_values_round_trip_but_not_with_wrong_key(self):
        with connection.cursor() as cursor:
            cursor.execute('SELECT cpf_encrypted FROM accounts_user WHERE id=%s', [self.user.pk])
            raw = cursor.fetchone()[0]
        self.assertEqual(decrypt_value(raw), '52998224725')
        with self.assertRaises(InvalidToken):
            EncryptedCharField().from_db_value(raw[:-4] + 'xxxx', None, connection)

    def test_order_and_preorder_phone_snapshots_are_encrypted_at_rest(self):
        order = Order.objects.create(customer=self.user, customer_name='Teste',
                                     customer_whatsapp='(11) 98765-4321', subtotal=1, total=1)
        preorder = PreOrderRequest.objects.create(customer_name='Teste', whatsapp='11987654321', product_name='Teste')
        for obj, table, field in [(order, 'orders_order', 'customer_whatsapp'),
                                  (preorder, 'orders_preorderrequest', 'whatsapp')]:
            with connection.cursor() as cursor:
                cursor.execute(f'SELECT {field} FROM {table} WHERE id=%s', [obj.pk])
                raw = cursor.fetchone()[0]
            self.assertNotIn('11987654321', raw)
            self.assertEqual(decrypt_value(raw), '11987654321')
            obj.refresh_from_db()
            self.assertEqual(getattr(obj, field), '11987654321')
            self.assertEqual(obj.phone_lookup, make_pii_lookup('11987654321'))


class SharedThrottleSecurityTests(TestCase):
    @override_settings(SHARED_RATE_LIMIT_ENABLED=True)
    def test_shared_login_limit_and_window_expiry(self):
        factory = RequestFactory()
        response = lambda request: HttpResponse('failed login')
        for _ in range(5):
            self.assertEqual(LoginRateLimitMiddleware(response)(factory.post('/conta/entrar/')).status_code, 200)
        self.assertEqual(LoginRateLimitMiddleware(response)(factory.post('/conta/entrar/')).status_code, 429)
        RateLimitBucket.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(LoginRateLimitMiddleware(response)(factory.post('/conta/entrar/')).status_code, 200)

    @override_settings(SHARED_RATE_LIMIT_ENABLED=True)
    def test_payment_webhook_is_not_blocked_by_store_browsing_limit(self):
        factory = RequestFactory()
        for _ in range(2):
            hit('global', '127.0.0.1', 1, 60)
        with override_settings(GLOBAL_RATE_LIMIT_MAX=1):
            middleware = GlobalRateLimitMiddleware(lambda request: HttpResponse('ok'))
            self.assertEqual(middleware(factory.get('/produtos/')).status_code, 429)
            self.assertEqual(middleware(factory.post('/pagamento/webhook/mercadopago/')).status_code, 200)

    @override_settings(TRUST_VERCEL_PROXY=True)
    def test_vercel_identity_cannot_be_changed_by_forwarded_for(self):
        request = RequestFactory().get('/', HTTP_X_FORWARDED_FOR='192.0.2.8', HTTP_X_VERCEL_FORWARDED_FOR='203.0.113.9')
        self.assertEqual(LoginRateLimitMiddleware._client_ip(request), '203.0.113.9')


class SessionRotationTests(SimpleTestCase):
    def test_previous_key_expires_without_restarting_process(self):
        old, new = 'previous-test-key' * 5, 'current-test-key' * 5
        with override_settings(SECRET_KEY=old, SECRET_KEY_FALLBACKS=[]):
            session = SessionStore()
            session['cart_token'] = 'preserved-cart'
            session.save()
            cookie = session.session_key
        fallbacks = ExpiringFallbackKeys([], old, 200)
        with override_settings(SECRET_KEY=new, SECRET_KEY_FALLBACKS=fallbacks):
            with patch('core.key_rotation.time.time', return_value=100):
                self.assertEqual(SessionStore(cookie)['cart_token'], 'preserved-cart')
            with patch('core.key_rotation.time.time', return_value=201):
                self.assertEqual(SessionStore(cookie).load(), {})

    def test_old_cart_cookie_survives_rotation_and_new_cookies_use_new_key(self):
        old = 'old-key-for-test' * 5
        new = 'new-key-for-test' * 5
        with override_settings(SECRET_KEY=old, SECRET_KEY_FALLBACKS=[]):
            session = SessionStore()
            session['cart_token'] = 'test-cart-id'
            session.save()
            cookie = session.session_key
        with override_settings(SECRET_KEY=new, SECRET_KEY_FALLBACKS=[old]):
            restored = SessionStore(cookie)
            self.assertEqual(restored['cart_token'], 'test-cart-id')
            restored.save()
            new_cookie = restored.session_key
        with override_settings(SECRET_KEY=new, SECRET_KEY_FALLBACKS=[]):
            self.assertEqual(SessionStore(new_cookie)['cart_token'], 'test-cart-id')
            self.assertEqual(SessionStore(cookie).load(), {})


class SharedThrottleConcurrencyTests(TransactionTestCase):
    @override_settings(SHARED_RATE_LIMIT_ENABLED=True)
    def test_parallel_workers_share_one_atomic_counter(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Production concurrency validation requires PostgreSQL')

        def request(_):
            close_old_connections()
            try:
                return hit('concurrency-test', '192.0.2.40', 10, 60)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(request, range(24)))
        self.assertEqual(sorted(result[1] for result in results), list(range(1, 25)))
        self.assertEqual(sum(result[0] for result in results), 14)
        self.assertEqual(RateLimitBucket.objects.get().count, 24)


class MonitoringPrivacyTests(SimpleTestCase):
    def test_external_monitoring_drops_personal_data(self):
        event = {'request': {'data': {'cpf': '52998224725'}}, 'user': {'email': 'x@example.com'},
                 'breadcrumbs': ['APP_USR-private'], 'exception': {'values': [{'type': 'ValueError',
                 'value': '52998224725', 'stacktrace': {'frames': [{'function': 'checkout', 'vars': {'token': 'secret'}}]}}]}}
        result = sanitize_sentry_event(event, {})
        serialized = json.dumps(result)
        for forbidden in ['52998224725', 'x@example.com', 'APP_USR', 'secret']:
            self.assertNotIn(forbidden, serialized)
        self.assertIn('checkout', serialized)


class AssetBuildSettingsTests(SimpleTestCase):
    def test_manage_default_settings_keep_production_manifest_generation(self):
        # Vercel collectstatic can use manage.py's development default even
        # though requests use vercel.py. Both must agree on hashed assets.
        from paraguashopping.settings import development
        self.assertEqual(
            development.STORAGES['staticfiles']['BACKEND'],
            'whitenoise.storage.CompressedManifestStaticFilesStorage',
        )
