import hashlib
import hmac
import json
import logging
from decimal import Decimal

import requests
from django.conf import settings
from django.utils import timezone

from orders.models import Order
from orders.services import confirm_order_payment
from payments.models import Payment
from .base import BasePaymentGateway, PaymentGatewayConfigurationError, PaymentGatewayTemporaryError


logger = logging.getLogger(__name__)


class MercadoPagoGateway(BasePaymentGateway):
    name = 'mercadopago'
    api_base = 'https://api.mercadopago.com'

    def __init__(self):
        self.access_token = getattr(settings, 'MP_ACCESS_TOKEN', '')
        self.public_key = getattr(settings, 'MP_PUBLIC_KEY', '')
        self.webhook_secret = getattr(settings, 'MP_WEBHOOK_SECRET', '')
        raw_url = getattr(settings, 'SITE_URL', '').rstrip('/')
        is_local = any(h in raw_url for h in ('localhost', '127.0.0.1', '0.0.0.0'))
        self.site_url = '' if is_local else raw_url
        self.use_sandbox_link = getattr(settings, 'MP_USE_SANDBOX_LINK', True)
        self.max_installments = getattr(settings, 'MP_MAX_INSTALLMENTS', 12)

    def create_payment(self, order, payment):
        self._validate_configuration()
        if order.payment_method == Order.PAYMENT_PIX:
            try:
                return self._create_pix_payment(order, payment)
            except PaymentGatewayTemporaryError:
                logger.info('PIX direto falhou para %s, usando Checkout Pro', order.order_number)
                return self._create_checkout_preference(order, payment)
        return self._create_checkout_preference(order, payment)

    def process_webhook(self, request, payload):
        if not self._valid_signature(request, payload):
            return 401

        payment_id = self._payment_id_from_request(request, payload)
        if not payment_id:
            return 200

        payment_data = self._get_gateway_payment(payment_id)
        if not payment_data:
            return 400

        external_reference = (
            payment_data.get('external_reference')
            or (payment_data.get('metadata') or {}).get('order_number')
        )
        if not external_reference:
            return 400

        payment = (
            Payment.objects.select_related('order')
            .filter(order__order_number=external_reference, is_active=True)
            .order_by('-created_at')
            .first()
        )
        if not payment:
            return 404

        gateway_status = payment_data.get('status', '')
        payment.gateway = self.name
        payment.gateway_id = str(payment_data.get('id') or payment_id)
        payment.gateway_status = gateway_status
        payment.raw_response = payment_data

        if gateway_status == 'approved':
            payment.status = Payment.STATUS_APPROVED
            payment.save()
            Payment.objects.filter(order=payment.order, is_active=True).exclude(
                pk=payment.pk,
            ).update(is_active=False, status=Payment.STATUS_CANCELLED)
            confirm_order_payment(payment.order, confirmed_at=timezone.now())
        elif gateway_status in {'rejected', 'cancelled'}:
            payment.status = Payment.STATUS_REJECTED if gateway_status == 'rejected' else Payment.STATUS_CANCELLED
            payment.save()
        elif gateway_status == 'refunded':
            payment.status = Payment.STATUS_REFUNDED
            payment.save()
        else:
            payment.status = Payment.STATUS_PENDING
            payment.save()
        return 200

    def _create_checkout_preference(self, order, payment):
        payload = {
            'items': [
                {
                    'id': str(item.product_id or item.pk),
                    'title': item.product_name,
                    'quantity': item.quantity,
                    'unit_price': float(item.unit_price),
                    'currency_id': 'BRL',
                }
                for item in order.items.all()
            ],
            'payer': {
                'name': order.customer_name,
                'email': order.customer_email,
            },
            'external_reference': order.order_number,
            'metadata': {'order_number': order.order_number},
            'payment_methods': {
                'installments': int(self.max_installments),
            },
        }

        if self.site_url:
            payload['notification_url'] = self._absolute_url('/pagamento/webhook/mercadopago/')
            payload['back_urls'] = {
                'success': self._absolute_url(f'/checkout/sucesso/{order.order_number}/'),
                'failure': self._absolute_url(f'/checkout/sucesso/{order.order_number}/'),
                'pending': self._absolute_url(f'/checkout/sucesso/{order.order_number}/'),
            }
            payload['auto_return'] = 'approved'

        response = self._request('post', '/checkout/preferences', json=payload)
        link = response.get('sandbox_init_point') if self.use_sandbox_link else response.get('init_point')
        link = link or response.get('init_point') or response.get('sandbox_init_point') or ''

        payment.gateway = self.name
        payment.gateway_id = response.get('id', '')
        payment.gateway_status = 'preference_created'
        payment.amount = order.total
        payment.payment_method = order.payment_method
        payment.payment_link = link
        payment.pix_code = ''
        payment.pix_qr_code = ''
        payment.raw_response = response
        payment.save()

        order.payment_link = link
        order.gateway_payment_id = payment.gateway_id
        order.save(update_fields=['payment_link', 'gateway_payment_id', 'updated_at'])
        return payment

    def _create_pix_payment(self, order, payment):
        payer = {
            'email': order.customer_email,
            'first_name': (order.customer_name or 'Cliente').split()[0],
        }
        cpf = getattr(order.customer, 'cpf', None)
        if cpf:
            payer['identification'] = {'type': 'CPF', 'number': cpf}

        payload = {
            'transaction_amount': float(Decimal(order.total)),
            'description': f'Pedido {order.order_number} - Jane Miranda',
            'payment_method_id': 'pix',
            'payer': payer,
            'external_reference': order.order_number,
            'metadata': {'order_number': order.order_number},
        }

        if self.site_url:
            payload['notification_url'] = self._absolute_url('/pagamento/webhook/mercadopago/')

        response = self._request(
            'post',
            '/v1/payments',
            json=payload,
            idempotency_key=f'{order.order_number}-pix',
        )
        transaction_data = (response.get('point_of_interaction') or {}).get('transaction_data') or {}

        payment.gateway = self.name
        payment.gateway_id = str(response.get('id', ''))
        payment.gateway_status = response.get('status', '')
        payment.amount = order.total
        payment.payment_method = order.payment_method
        payment.pix_code = transaction_data.get('qr_code', '')
        payment.pix_qr_code = transaction_data.get('qr_code_base64', '')
        payment.payment_link = transaction_data.get('ticket_url', '')
        payment.raw_response = response
        payment.save()

        order.payment_link = payment.payment_link
        order.gateway_payment_id = payment.gateway_id
        order.save(update_fields=['payment_link', 'gateway_payment_id', 'updated_at'])
        return payment

    def _get_gateway_payment(self, payment_id):
        try:
            return self._request('get', f'/v1/payments/{payment_id}')
        except PaymentGatewayTemporaryError:
            logger.exception('Unable to fetch Mercado Pago payment %s', payment_id)
            return None

    def _request(self, method, path, json=None, idempotency_key=None):
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
        }
        if idempotency_key:
            headers['X-Idempotency-Key'] = idempotency_key

        try:
            response = requests.request(
                method,
                f'{self.api_base}{path}',
                headers=headers,
                json=json,
                timeout=20,
            )
        except requests.RequestException as exc:
            raise PaymentGatewayTemporaryError('Falha ao conectar ao Mercado Pago.') from exc

        if response.status_code >= 400:
            logger.error('Mercado Pago returned %s: %s', response.status_code, response.text[:500])
            raise PaymentGatewayTemporaryError('Mercado Pago recusou a requisição.')
        return response.json()

    def _validate_configuration(self):
        missing = []
        if not self.access_token:
            missing.append('MP_ACCESS_TOKEN')
        if not self.public_key:
            missing.append('MP_PUBLIC_KEY')
        if missing:
            raise PaymentGatewayConfigurationError(
                f'Configuração incompleta do Mercado Pago: {", ".join(missing)}.'
            )

    def _absolute_url(self, path):
        return f'{self.site_url}{path}'

    def _payment_id_from_request(self, request, payload):
        data_id = request.GET.get('data.id') or request.GET.get('id')
        if data_id:
            return data_id
        try:
            data = json.loads(payload or b'{}')
        except (TypeError, ValueError):
            return ''
        return str((data.get('data') or {}).get('id') or data.get('id') or '')

    def _valid_signature(self, request, payload):
        if not self.webhook_secret:
            return bool(getattr(settings, 'PAYMENT_SANDBOX', True))

        signature = request.headers.get('X-Signature', '')
        request_id = request.headers.get('X-Request-Id', '')
        parts = self._parse_signature(signature)
        ts = parts.get('ts')
        received = parts.get('v1')
        if not ts or not received:
            return False

        payment_id = self._payment_id_from_request(request, payload)
        manifest = ''
        if payment_id:
            manifest += f'id:{payment_id};'
        if request_id:
            manifest += f'request-id:{request_id};'
        manifest += f'ts:{ts};'

        expected = hmac.new(
            self.webhook_secret.encode(),
            manifest.encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, received)

    @staticmethod
    def _parse_signature(signature):
        parts = {}
        for item in signature.split(','):
            if '=' not in item:
                continue
            key, value = item.strip().split('=', 1)
            parts[key] = value
        return parts
