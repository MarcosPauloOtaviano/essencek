class PaymentGatewayError(Exception):
    """Base exception for payment gateway failures."""


class PaymentGatewayConfigurationError(PaymentGatewayError):
    """Raised when required gateway credentials or settings are missing."""


class PaymentGatewayTemporaryError(PaymentGatewayError):
    """Raised when the gateway cannot complete the request right now."""


class BasePaymentGateway:
    name = 'base'

    def create_payment(self, order, payment):
        raise NotImplementedError

    def process_webhook(self, request, payload):
        raise NotImplementedError
