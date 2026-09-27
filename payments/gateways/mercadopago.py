import hashlib
import hmac
import json
import logging
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from orders.models import Order
from orders.services import InsufficientStockError, confirm_order_payment
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
        self.webhook_token = getattr(settings, 'MP_WEBHOOK_TOKEN', '')
        raw_url = getattr(settings, 'SITE_URL', '').rstrip('/')
        is_local = any(h in raw_url for h in ('localhost', '127.0.0.1', '0.0.0.0'))  # nosec B104
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

        external_reference = self._external_reference(payment_data)
        if not external_reference:
            return 400

        order = Order.objects.filter(order_number=external_reference).first()
        if not order:
            return 404

        return 200 if self._apply_payment_data(order, payment_data) else 400

    def sync_order_payment(self, order, payment_id=''):
        """Reconcile an order with Mercado Pago without trusting browser status fields."""
        self._validate_configuration()
        candidates = []
        payment_id = str(payment_id or '').strip()
        if payment_id.isdigit():
            payment_data = self._get_gateway_payment(payment_id)
            if payment_data:
                candidates.append(payment_data)

        for payment_data in self._search_gateway_payments(order.order_number):
            candidate_id = str(payment_data.get('id') or '')
            if candidate_id and all(str(item.get('id') or '') != candidate_id for item in candidates):
                candidates.append(payment_data)

        # Prefer an approved payment when the API returns more than one attempt.
        candidates.sort(key=lambda item: item.get('status') == 'approved', reverse=True)
        for payment_data in candidates:
            if self._payment_matches_order(order, payment_data):
                return self._apply_payment_data(order, payment_data)
        return False

    def _apply_payment_data(self, order, payment_data):
        if not self._payment_matches_order(order, payment_data):
            logger.warning(
                'Mercado Pago payment validation failed for order %s and payment %s',
                order.order_number,
                payment_data.get('id', ''),
            )
            return False

        gateway_status = str(payment_data.get('status') or '')
        gateway_id = str(payment_data.get('id') or '')
        approved = gateway_status == 'approved'
        with transaction.atomic():
            locked_order = Order.objects.select_for_update().get(pk=order.pk)
            payments = Payment.objects.select_for_update().filter(order=locked_order)
            payment = payments.filter(gateway_id=gateway_id).order_by('-created_at').first()
            if not payment:
                payment = payments.filter(is_active=True).order_by('-created_at').first()
            if not payment:
                payment = payments.order_by('-created_at').first()
            if not payment:
                payment = Payment.objects.create(
                    order=locked_order,
                    gateway=self.name,
                    gateway_id=gateway_id,
                    amount=locked_order.total,
                    payment_method=locked_order.payment_method,
                    status=Payment.STATUS_PENDING,
                    is_active=True,
                )

            payment.gateway = self.name
            payment.gateway_id = gateway_id
            payment.gateway_status = gateway_status
            payment.raw_response = self._safe_payment_response(payment_data)

            if approved:
                payment.status = Payment.STATUS_APPROVED
                payment.is_active = True
                payment.save()
                Payment.objects.filter(order=locked_order, is_active=True).exclude(
                    pk=payment.pk,
                ).update(is_active=False, status=Payment.STATUS_CANCELLED)
            elif gateway_status in {'rejected', 'cancelled'}:
                payment.status = (
                    Payment.STATUS_REJECTED
                    if gateway_status == 'rejected'
                    else Payment.STATUS_CANCELLED
                )
                payment.save()
            elif gateway_status == 'refunded':
                payment.status = Payment.STATUS_REFUNDED
                payment.save()
            else:
                payment.status = Payment.STATUS_PENDING
                payment.save()

        if approved:
            try:
                confirm_order_payment(order, confirmed_at=timezone.now())
            except InsufficientStockError as exc:
                # The gateway has charged the customer. Preserve that financial truth and
                # flag the order for manual fulfillment/refund without reducing stock below zero.
                logger.critical(
                    'Approved payment %s requires manual fulfillment for order %s: %s',
                    gateway_id,
                    order.order_number,
                    exc,
                )
                self._mark_paid_with_fulfillment_issue(order)
        return True

    @staticmethod
    def _mark_paid_with_fulfillment_issue(order):
        marker = '[Pagamento aprovado: verificar estoque antes da separação.]'
        with transaction.atomic():
            locked_order = Order.objects.select_for_update().get(pk=order.pk)
            if locked_order.payment_status == 'confirmed':
                return
            locked_order.payment_status = 'confirmed'
            locked_order.status = Order.STATUS_PARTIAL_CONFIRMED
            locked_order.payment_confirmed_at = timezone.now()
            if marker not in locked_order.internal_notes:
                separator = '\n' if locked_order.internal_notes else ''
                locked_order.internal_notes = f'{locked_order.internal_notes}{separator}{marker}'
            locked_order.save(update_fields=[
                'payment_status',
                'status',
                'payment_confirmed_at',
                'internal_notes',
                'updated_at',
            ])

    def _payment_matches_order(self, order, payment_data):
        if self._external_reference(payment_data) != order.order_number:
            return False
        if payment_data.get('currency_id') != 'BRL':
            return False
        try:
            received_amount = Decimal(str(payment_data.get('transaction_amount'))).quantize(
                Decimal('0.01')
            )
            expected_amount = Decimal(order.total).quantize(Decimal('0.01'))
        except (InvalidOperation, TypeError, ValueError):
            return False
        if received_amount != expected_amount:
            return False
        if not getattr(settings, 'PAYMENT_SANDBOX', True) and payment_data.get('live_mode') is not True:
            return False
        return True

    @staticmethod
    def _external_reference(payment_data):
        external_reference = payment_data.get('external_reference')
        if external_reference:
            return str(external_reference)
        return str((payment_data.get('metadata') or {}).get('order_number') or '')

    @staticmethod
    def _safe_payment_response(payment_data):
        safe_keys = {
            'id',
            'status',
            'status_detail',
            'external_reference',
            'currency_id',
            'transaction_amount',
            'date_approved',
            'live_mode',
            'payment_method_id',
            'preference_id',
            'collector_id',
        }
        safe_response = {key: payment_data.get(key) for key in safe_keys if key in payment_data}
        metadata = payment_data.get('metadata') or {}
        if metadata.get('order_number'):
            safe_response['metadata'] = {'order_number': metadata['order_number']}
        return safe_response

    def _create_checkout_preference(self, order, payment):
        items = [
            {
                'id': str(item.product_id or item.pk),
                'title': item.product_name,
                'quantity': item.quantity,
                'unit_price': float(item.unit_price),
                'currency_id': 'BRL',
            }
            for item in order.items.all()
        ]
        if order.shipping_cost > 0:
            items.append({
                'id': f'frete-{order.order_number}',
                'title': f'Frete — {order.shipping_service or "Entrega"}',
                'quantity': 1,
                'unit_price': float(order.shipping_cost),
                'currency_id': 'BRL',
            })

        payload = {
            'items': items,
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
            payload['notification_url'] = self._notification_url()
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
        payment.raw_response = self._safe_payment_response(response)
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
            'description': f'Pedido {order.order_number} - Essence K Importados',
            'payment_method_id': 'pix',
            'payer': payer,
            'external_reference': order.order_number,
            'metadata': {'order_number': order.order_number},
        }

        if self.site_url:
            payload['notification_url'] = self._notification_url()

        response = self._request(
            'post',
            '/v1/payments',
            json=payload,
            idempotency_key=f'{order.order_number}-pix-{payment.pk}',
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
        payment.raw_response = self._safe_payment_response(response)
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

    def _search_gateway_payments(self, external_reference):
        try:
            response = self._request(
                'get',
                '/v1/payments/search',
                params={
                    'external_reference': external_reference,
                    'sort': 'date_created',
                    'criteria': 'desc',
                    'limit': 10,
                },
            )
        except PaymentGatewayTemporaryError:
            logger.exception('Unable to search Mercado Pago payments for order %s', external_reference)
            return []
        return response.get('results') or []

    def _request(self, method, path, json=None, params=None, idempotency_key=None):
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
                params=params,
                timeout=20,
            )
        except requests.RequestException as exc:
            raise PaymentGatewayTemporaryError('Falha ao conectar ao Mercado Pago.') from exc

        if response.status_code >= 400:
            logger.error('Mercado Pago returned HTTP %s for %s', response.status_code, path)
            raise PaymentGatewayTemporaryError('Mercado Pago recusou a requisição.')
        return response.json()

    def _validate_configuration(self):
        missing = []
        if not self.access_token:
            missing.append('MP_ACCESS_TOKEN')
        if not self.public_key:
            missing.append('MP_PUBLIC_KEY')
        if (
            not getattr(settings, 'PAYMENT_SANDBOX', True)
            and not self.webhook_secret
            and not self.webhook_token
        ):
            missing.append('MP_WEBHOOK_SECRET ou MP_WEBHOOK_TOKEN')
        if missing:
            raise PaymentGatewayConfigurationError(
                f'Configuração incompleta do Mercado Pago: {", ".join(missing)}.'
            )

    def _absolute_url(self, path):
        return f'{self.site_url}{path}'

    def _notification_url(self):
        url = self._absolute_url('/pagamento/webhook/mercadopago/')
        if self.webhook_token:
            return f'{url}?{urlencode({"token": self.webhook_token})}'
        return url

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
            supplied_token = request.GET.get('token', '')
            if self.webhook_token and hmac.compare_digest(self.webhook_token, supplied_token):
                return True
            logger.error('Mercado Pago webhook rejected: no valid signature or callback token')
            return False

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
