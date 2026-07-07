from decimal import Decimal

from django.test import TestCase, override_settings

from accounts.models import User
from orders.models import Order
from payments.models import Payment
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

        self.assertEqual(payment.gateway, 'sandbox')
        self.assertEqual(payment.gateway_status, 'simulated_pending')
        self.assertIn('PIX-SIMULADO', payment.pix_code)
        self.assertFalse(payment.payment_link)
        self.assertEqual(Payment.objects.count(), 1)
