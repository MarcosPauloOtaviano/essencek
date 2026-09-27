import hashlib
import hmac
import json
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from orders.models import Order
from orders.services import InsufficientStockError
from payments.models import Payment
from payments.gateways.mercadopago import MercadoPagoGateway
from payments.services import PaymentService


@override_settings(
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
    PAYMENT_SANDBOX=True,
    PAYMENT_GATEWAY='sandbox',
    FERNET_KEYS=['y_0UztNJ7Z1bTin2n33g6tE2x3BNbpBgiiSy8WEPOXA='],
)
class PaymentServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='cliente@example.com',
            email='cliente@example.com',
            password='SenhaForte123!',
            full_name='Cliente Teste',
            whatsapp='11987654321',
        )

    def create_order(self, payment_method=Order.PAYMENT_PIX):
        return Order.objects.create(
            customer=self.user,
            customer_name='Cliente Teste',
            customer_email='cliente@example.com',
            customer_whatsapp='11987654321',
            address='Rua Teste',
            address_number='123',
            city='Sao Paulo',
            state='SP',
            cep='01001-000',
            subtotal=Decimal('99.90'),
            shipping_cost=Decimal('0.00'),
            total=Decimal('99.90'),
            payment_method=payment_method,
        )

    def test_sandbox_pix_is_explicitly_simulated(self):
        order = self.create_order()

        payment = PaymentService().create_payment(order)
        same_payment = PaymentService().create_payment(order)

        self.assertEqual(payment.gateway, 'sandbox')
        self.assertEqual(payment.gateway_status, 'simulated_pending')
        self.assertIn('PIX-SIMULADO', payment.pix_code)
        self.assertFalse(payment.payment_link)
        self.assertEqual(same_payment.pk, payment.pk)
        self.assertEqual(Payment.objects.count(), 1)

    def test_legacy_order_must_choose_an_online_method_before_payment(self):
        order = self.create_order(payment_method=Order.PAYMENT_WHATSAPP)
        order.status = Order.STATUS_AWAITING_CONTACT
        order.save(update_fields=['status'])
        self.client.login(username='cliente@example.com', password='SenhaForte123!')

        response = self.client.get(reverse('payment_pix', args=[order.order_number]))

        self.assertRedirects(
            response,
            reverse('order_detail', args=[order.order_number]),
            fetch_redirect_response=False,
        )
        self.assertFalse(Payment.objects.exists())

    def test_legacy_order_can_switch_to_pix_without_being_recreated(self):
        order = self.create_order(payment_method=Order.PAYMENT_WHATSAPP)
        order.status = Order.STATUS_AWAITING_CONTACT
        order.save(update_fields=['status'])
        self.client.login(username='cliente@example.com', password='SenhaForte123!')

        response = self.client.post(
            reverse('change_payment_method', args=[order.order_number]),
            {'payment_method': Order.PAYMENT_PIX},
        )

        order.refresh_from_db()
        self.assertRedirects(
            response,
            reverse('payment_pix', args=[order.order_number]),
            fetch_redirect_response=False,
        )
        self.assertEqual(order.payment_method, Order.PAYMENT_PIX)
        self.assertEqual(order.status, Order.STATUS_AWAITING_PAYMENT)
        self.assertEqual(Payment.objects.filter(order=order).count(), 1)


@override_settings(
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
    PAYMENT_SANDBOX=False,
    PAYMENT_GATEWAY='mercadopago',
    SITE_URL='https://example.com',
    MP_ACCESS_TOKEN='production-token',
    MP_PUBLIC_KEY='production-public-key',
    MP_WEBHOOK_SECRET='webhook-secret',
    MP_WEBHOOK_TOKEN='callback-token',
    MP_USE_SANDBOX_LINK=False,
    FERNET_KEYS=['y_0UztNJ7Z1bTin2n33g6tE2x3BNbpBgiiSy8WEPOXA='],
)
class MercadoPagoProductionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='pagante@example.com',
            email='pagante@example.com',
            password='SenhaForte123!',
            full_name='Cliente Pagante',
            whatsapp='11987654321',
        )
        self.order = Order.objects.create(
            customer=self.user,
            customer_name='Cliente Pagante',
            customer_email='pagante@example.com',
            customer_whatsapp='11987654321',
            address='Rua Teste',
            address_number='123',
            city='Sao Paulo',
            state='SP',
            cep='01001-000',
            subtotal=Decimal('99.90'),
            shipping_cost=Decimal('0.00'),
            total=Decimal('99.90'),
            payment_method=Order.PAYMENT_PIX,
            status=Order.STATUS_AWAITING_PAYMENT,
        )
        self.payment = Payment.objects.create(
            order=self.order,
            gateway='mercadopago',
            gateway_id='123456',
            amount=self.order.total,
            payment_method=Order.PAYMENT_PIX,
            status=Payment.STATUS_PENDING,
            is_active=True,
        )

    def payment_data(self, **overrides):
        data = {
            'id': 123456,
            'status': 'approved',
            'status_detail': 'accredited',
            'external_reference': self.order.order_number,
            'currency_id': 'BRL',
            'transaction_amount': 99.90,
            'live_mode': True,
            'payment_method_id': 'pix',
            'payer': {'email': 'must-not-be-persisted@example.com'},
        }
        data.update(overrides)
        return data

    def test_sync_confirms_only_matching_production_payment(self):
        gateway = MercadoPagoGateway()
        with (
            patch.object(gateway, '_get_gateway_payment', return_value=self.payment_data()),
            patch.object(gateway, '_search_gateway_payments', return_value=[]),
        ):
            synced = gateway.sync_order_payment(self.order, payment_id='123456')

        self.order.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertTrue(synced)
        self.assertEqual(self.order.payment_status, 'confirmed')
        self.assertEqual(self.order.status, Order.STATUS_PAYMENT_CONFIRMED)
        self.assertEqual(self.payment.status, Payment.STATUS_APPROVED)
        self.assertNotIn('payer', self.payment.raw_response)

    def test_sync_rejects_payment_with_wrong_amount(self):
        gateway = MercadoPagoGateway()
        with (
            patch.object(
                gateway,
                '_get_gateway_payment',
                return_value=self.payment_data(transaction_amount=Decimal('9.90')),
            ),
            patch.object(gateway, '_search_gateway_payments', return_value=[]),
        ):
            synced = gateway.sync_order_payment(self.order, payment_id='123456')

        self.order.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertFalse(synced)
        self.assertEqual(self.order.payment_status, 'pending')
        self.assertEqual(self.payment.status, Payment.STATUS_PENDING)

    def test_sync_rejects_non_live_payment_in_production(self):
        gateway = MercadoPagoGateway()
        with (
            patch.object(
                gateway,
                '_get_gateway_payment',
                return_value=self.payment_data(live_mode=False),
            ),
            patch.object(gateway, '_search_gateway_payments', return_value=[]),
        ):
            synced = gateway.sync_order_payment(self.order, payment_id='123456')

        self.order.refresh_from_db()
        self.assertFalse(synced)
        self.assertEqual(self.order.payment_status, 'pending')

    def test_approved_payment_remains_confirmed_when_fulfillment_needs_attention(self):
        gateway = MercadoPagoGateway()
        with (
            patch.object(gateway, '_get_gateway_payment', return_value=self.payment_data()),
            patch.object(gateway, '_search_gateway_payments', return_value=[]),
            patch(
                'payments.gateways.mercadopago.confirm_order_payment',
                side_effect=InsufficientStockError('Estoque indisponível'),
            ),
        ):
            synced = gateway.sync_order_payment(self.order, payment_id='123456')

        self.order.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertTrue(synced)
        self.assertEqual(self.payment.status, Payment.STATUS_APPROVED)
        self.assertEqual(self.order.payment_status, 'confirmed')
        self.assertEqual(self.order.status, Order.STATUS_PARTIAL_CONFIRMED)
        self.assertIn('verificar estoque', self.order.internal_notes)

    def test_checkout_preference_charges_shipping_as_part_of_order_total(self):
        self.order.shipping_cost = Decimal('15.00')
        self.order.total = Decimal('114.90')
        self.order.shipping_service = 'Entrega expressa'
        self.order.save(update_fields=['shipping_cost', 'total', 'shipping_service', 'updated_at'])
        self.order.items.create(
            product_name='Produto teste',
            unit_price=Decimal('99.90'),
            quantity=1,
        )
        self.payment.amount = self.order.total
        self.payment.save(update_fields=['amount', 'updated_at'])
        gateway = MercadoPagoGateway()

        with patch.object(
            gateway,
            '_request',
            return_value={'id': 'preference-id', 'init_point': 'https://example.com/pay'},
        ) as request:
            gateway._create_checkout_preference(self.order, self.payment)

        payload = request.call_args.kwargs['json']
        charged_total = sum(
            Decimal(str(item['unit_price'])) * item['quantity']
            for item in payload['items']
        )
        self.assertEqual(charged_total, self.order.total)
        self.assertEqual(payload['items'][-1]['title'], 'Frete — Entrega expressa')
        self.assertEqual(
            payload['notification_url'],
            'https://example.com/pagamento/webhook/mercadopago/?token=callback-token',
        )

    def test_each_new_pix_attempt_has_its_own_idempotency_key(self):
        gateway = MercadoPagoGateway()
        response = {
            'id': 123456,
            'status': 'pending',
            'external_reference': self.order.order_number,
            'currency_id': 'BRL',
            'transaction_amount': 99.90,
            'live_mode': True,
            'point_of_interaction': {
                'transaction_data': {
                    'qr_code': 'pix-code',
                    'qr_code_base64': 'base64-image',
                    'ticket_url': 'https://example.com/pix',
                },
            },
        }
        with patch.object(gateway, '_request', return_value=response) as request:
            gateway._create_pix_payment(self.order, self.payment)

        self.assertEqual(
            request.call_args.kwargs['idempotency_key'],
            f'{self.order.order_number}-pix-{self.payment.pk}',
        )

    def test_signed_webhook_confirms_payment(self):
        payment_id = '123456'
        request_id = 'request-abc'
        timestamp = '1700000000'
        manifest = f'id:{payment_id};request-id:{request_id};ts:{timestamp};'
        signature = hmac.new(
            b'webhook-secret',
            manifest.encode(),
            hashlib.sha256,
        ).hexdigest()
        body = json.dumps({'type': 'payment', 'data': {'id': payment_id}}).encode()

        with patch.object(
            MercadoPagoGateway,
            '_get_gateway_payment',
            return_value=self.payment_data(),
        ):
            response = self.client.post(
                f"{reverse('webhook_mp')}?data.id={payment_id}",
                data=body,
                content_type='application/json',
                HTTP_X_SIGNATURE=f'ts={timestamp},v1={signature}',
                HTTP_X_REQUEST_ID=request_id,
            )

        self.order.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.order.payment_status, 'confirmed')

    def test_invalid_webhook_signature_is_rejected(self):
        response = self.client.post(
            f"{reverse('webhook_mp')}?data.id=123456",
            data=b'{}',
            content_type='application/json',
            HTTP_X_SIGNATURE='ts=1700000000,v1=invalid',
            HTTP_X_REQUEST_ID='request-abc',
        )

        self.order.refresh_from_db()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.order.payment_status, 'pending')

    @override_settings(MP_WEBHOOK_SECRET='')
    def test_private_callback_token_reconciles_payment_without_panel_signature(self):
        body = json.dumps({'type': 'payment', 'data': {'id': '123456'}}).encode()
        with patch.object(
            MercadoPagoGateway,
            '_get_gateway_payment',
            return_value=self.payment_data(),
        ):
            response = self.client.post(
                f"{reverse('webhook_mp')}?token=callback-token&data.id=123456",
                data=body,
                content_type='application/json',
            )

        self.order.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.order.payment_status, 'confirmed')

    @override_settings(MP_WEBHOOK_SECRET='')
    def test_wrong_callback_token_is_rejected(self):
        response = self.client.post(
            f"{reverse('webhook_mp')}?token=wrong&data.id=123456",
            data=b'{}',
            content_type='application/json',
        )

        self.order.refresh_from_db()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.order.payment_status, 'pending')

    def test_payment_status_endpoint_syncs_only_owned_order(self):
        self.client.login(username='pagante@example.com', password='SenhaForte123!')

        def confirm_order(order, payment_id=''):
            order.payment_status = 'confirmed'
            order.status = Order.STATUS_PAYMENT_CONFIRMED
            order.save(update_fields=['payment_status', 'status', 'updated_at'])
            return True

        with patch(
            'payments.views.PaymentService.sync_order_payment',
            side_effect=confirm_order,
        ) as sync:
            response = self.client.get(
                reverse('payment_status', args=[self.order.order_number]),
                {'payment_id': '123456'},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['paid'])
        sync.assert_called_once()

        other_user = User.objects.create_user(
            username='outro@example.com',
            email='outro@example.com',
            password='SenhaForte123!',
        )
        self.client.force_login(other_user)
        response = self.client.get(reverse('payment_status', args=[self.order.order_number]))
        self.assertEqual(response.status_code, 404)

    def test_return_page_shows_confirmed_payment_after_reconciliation(self):
        self.client.login(username='pagante@example.com', password='SenhaForte123!')

        def confirm_order(order, payment_id=''):
            order.payment_status = 'confirmed'
            order.status = Order.STATUS_PAYMENT_CONFIRMED
            order.save(update_fields=['payment_status', 'status', 'updated_at'])
            return True

        with patch(
            'orders.views.PaymentService.sync_order_payment',
            side_effect=confirm_order,
        ):
            response = self.client.get(
                reverse('orders:success', args=[self.order.order_number]),
                {'payment_id': '123456'},
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pagamento confirmado!')
        self.assertNotContains(response, 'Pagar com Pix')

    def test_order_detail_reconciles_payment_when_customer_returns_later(self):
        self.client.login(username='pagante@example.com', password='SenhaForte123!')

        def confirm_order(order, payment_id=''):
            order.payment_status = 'confirmed'
            order.status = Order.STATUS_PAYMENT_CONFIRMED
            order.save(update_fields=['payment_status', 'status', 'updated_at'])
            return True

        with patch(
            'accounts.views.PaymentService.sync_order_payment',
            side_effect=confirm_order,
        ) as sync:
            response = self.client.get(reverse('order_detail', args=[self.order.order_number]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pagamento confirmado')
        sync.assert_called_once()
