import logging

from django.conf import settings

from .gateways import MercadoPagoGateway, SandboxGateway
from .gateways.base import PaymentGatewayConfigurationError, PaymentGatewayTemporaryError
from .models import Payment


logger = logging.getLogger(__name__)


class PaymentService:
    def __init__(self):
        self.gateway_name = getattr(settings, 'PAYMENT_GATEWAY', 'sandbox')
        self.sandbox = getattr(settings, 'PAYMENT_SANDBOX', True)

    def create_payment(self, order, force_new=False):
        if not force_new:
            existing = Payment.objects.filter(
                order=order, is_active=True,
                status=Payment.STATUS_PENDING,
            ).order_by('-created_at').first()
            if existing and existing.payment_link:
                return existing

        Payment.objects.filter(order=order, is_active=True).exclude(
            status=Payment.STATUS_APPROVED,
        ).update(is_active=False)

        payment = Payment.objects.create(
            order=order,
            gateway=self.gateway_name,
            amount=order.total,
            payment_method=order.payment_method,
            status=Payment.STATUS_PENDING,
            is_active=True,
        )

        gateway = self._gateway()
        try:
            return gateway.create_payment(order, payment)
        except (PaymentGatewayConfigurationError, PaymentGatewayTemporaryError) as exc:
            logger.error('Payment gateway error for order %s: %s', order.order_number, exc)
            payment.gateway = self.gateway_name
            payment.gateway_status = 'configuration_error'
            payment.raw_response = {'error': str(exc)}
            payment.save()
            if self.sandbox:
                return SandboxGateway().create_payment(order, payment)
            return payment

    def confirm_payment_webhook(self, gateway_name, request):
        if gateway_name != 'mercadopago':
            return 400
        return MercadoPagoGateway().process_webhook(request, request.body)

    def _gateway(self):
        if self.gateway_name == 'mercadopago':
            return MercadoPagoGateway()
        return SandboxGateway()
