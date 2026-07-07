from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from cart.models import Cart, CartItem
from products.models import Category, Product
from .forms import CheckoutForm
from .models import Order
from .services import confirm_order_payment


@override_settings(
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
    FERNET_KEYS=['y_0UztNJ7Z1bTin2n33g6tE2x3BNbpBgiiSy8WEPOXA='],
)
class OrderFlowSecurityTests(TestCase):
    def setUp(self):
        self.category, _ = Category.objects.get_or_create(
            slug='perfumes',
            defaults={'name': 'Perfumes'},
        )
        self.owner = User.objects.create_user(
            username='cliente@example.com',
            email='cliente@example.com',
            password='SenhaForte123!',
            full_name='Cliente Teste',
            whatsapp='11987654321',
        )
        self.other = User.objects.create_user(
            username='outro@example.com',
            email='outro@example.com',
            password='SenhaForte123!',
            full_name='Outro Cliente',
            whatsapp='21987654321',
        )

    def create_order(self):
        return Order.objects.create(
            customer=self.owner,
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
            payment_method=Order.PAYMENT_PIX,
        )

    def test_order_success_is_visible_only_to_owner_or_admin(self):
        order = self.create_order()

        self.client.login(username='outro@example.com', password='SenhaForte123!')
        other_response = self.client.get(reverse('orders:success', args=[order.order_number]))
        self.assertEqual(other_response.status_code, 404)

        self.client.login(username='cliente@example.com', password='SenhaForte123!')
        owner_response = self.client.get(reverse('orders:success', args=[order.order_number]))
        self.assertEqual(owner_response.status_code, 200)

    def test_checkout_redirects_when_cart_stock_is_no_longer_available(self):
        product = Product.objects.create(
            name='Produto Limitado',
            category=self.category,
            price='99.90',
            stock=1,
            status=Product.STATUS_AVAILABLE,
        )
        cart = Cart.objects.create(user=self.owner)
        CartItem.objects.create(cart=cart, product=product, quantity=1)
        product.stock = 0
        product.save(update_fields=['stock'])

        self.client.login(username='cliente@example.com', password='SenhaForte123!')
        response = self.client.get(reverse('orders:checkout'))

        self.assertRedirects(response, reverse('cart:detail'), fetch_redirect_response=False)
        self.assertFalse(Order.objects.exists())

    def test_checkout_creates_order_with_selected_shipping(self):
        product = Product.objects.create(
            name='Produto Entregavel',
            category=self.category,
            price='99.90',
            stock=2,
            status=Product.STATUS_AVAILABLE,
        )
        cart = Cart.objects.create(user=self.owner)
        CartItem.objects.create(cart=cart, product=product, quantity=1)

        self.client.login(username='cliente@example.com', password='SenhaForte123!')
        session = self.client.session
        session['shipping_cost'] = '15.90'
        session['shipping_service'] = 'pac'
        session.save()

        response = self.client.post(reverse('orders:checkout'), data={
            'customer_name': 'Cliente Teste',
            'customer_email': 'cliente@example.com',
            'customer_whatsapp': '(11) 98765-4321',
            'address': 'Rua Teste',
            'address_number': '123',
            'address_complement': '',
            'neighborhood': 'Centro',
            'city': 'Sao Paulo',
            'state': 'SP',
            'cep': '01001-000',
            'payment_method': Order.PAYMENT_PIX,
            'customer_notes': '',
        })

        order = Order.objects.get()
        self.assertRedirects(response, reverse('orders:success', args=[order.order_number]), fetch_redirect_response=False)
        self.assertEqual(order.shipping_cost, Decimal('15.90'))
        self.assertEqual(order.shipping_service, 'pac')
        self.assertEqual(order.total, Decimal('115.80'))
        self.assertFalse(cart.items.exists())

    def test_checkout_form_normalizes_delivery_contact_fields(self):
        form = CheckoutForm(data={
            'customer_name': 'Cliente Teste',
            'customer_email': 'CLIENTE@EXAMPLE.COM',
            'customer_whatsapp': '+55 (11) 98765-4321',
            'address': 'Rua Teste',
            'address_number': '123',
            'address_complement': '',
            'neighborhood': 'Centro',
            'city': 'Sao Paulo',
            'state': 'sp',
            'cep': '01001-000',
            'payment_method': Order.PAYMENT_PIX,
            'customer_notes': '',
        })

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['customer_email'], 'cliente@example.com')
        self.assertEqual(form.cleaned_data['customer_whatsapp'], '11987654321')
        self.assertEqual(form.cleaned_data['cep'], '01001-000')
        self.assertEqual(form.cleaned_data['state'], 'SP')

    def test_confirm_order_payment_decrements_stock_only_once(self):
        product = Product.objects.create(
            name='Produto Pago',
            category=self.category,
            price='99.90',
            stock=5,
            status=Product.STATUS_AVAILABLE,
        )
        order = self.create_order()
        order.items.create(
            product=product,
            product_name=product.name,
            unit_price=product.price,
            quantity=2,
            is_pre_order=False,
        )

        self.assertTrue(confirm_order_payment(order))
        self.assertFalse(confirm_order_payment(order))
        product.refresh_from_db()

        self.assertEqual(product.stock, 3)
