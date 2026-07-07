from .base import BasePaymentGateway


class SandboxGateway(BasePaymentGateway):
    name = 'sandbox'

    def create_payment(self, order, payment):
        payment.gateway = self.name
        payment.gateway_id = f'sandbox_{order.order_number}'
        payment.gateway_status = 'simulated_pending'
        payment.amount = order.total
        payment.payment_method = order.payment_method
        payment.raw_response = {
            'mode': 'sandbox',
            'message': 'Pagamento simulado para desenvolvimento. Não movimenta dinheiro.',
        }

        if order.payment_method == 'pix':
            payment.pix_code = f'PIX-SIMULADO-JANE-MIRANDA-{order.order_number}'
            payment.pix_qr_code = ''
            payment.payment_link = ''
        else:
            payment.payment_link = ''
            payment.pix_code = ''
            payment.pix_qr_code = ''

        payment.save()
        order.payment_link = payment.payment_link
        order.gateway_payment_id = payment.gateway_id
        order.save(update_fields=['payment_link', 'gateway_payment_id', 'updated_at'])
        return payment

    def process_webhook(self, request, payload):
        return 200
