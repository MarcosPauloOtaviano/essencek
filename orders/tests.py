from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from cart.models import Cart, CartItem
from cart.utils import cart_signature
from products.models import Category, Product
from .forms import CheckoutForm
from .models import Order
from .services import (
    InsufficientStockError,
    build_order_whatsapp_url,
    confirm_order_payment,
)
from .views import CHECKOUT_TOKEN_SESSION_KEY


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
        checkout_page = self.client.get(reverse('orders:checkout'))
        self.assertEqual(checkout_page.status_code, 200)
        session = self.client.session
        session['shipping_cost'] = '15.90'
        session['shipping_service'] = 'PAC'
        session['shipping_cep'] = '01001000'
        session['shipping_cart_signature'] = cart_signature(cart)
        session.save()

        response = self.client.post(reverse('orders:checkout'), data={
            'checkout_token': self.client.session[CHECKOUT_TOKEN_SESSION_KEY],
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
            'shipping_method': 'delivery',
            'customer_notes': '',
        })

        order = Order.objects.get()
        expected_url = f'{reverse("orders:whatsapp", args=[order.order_number])}?open=1'
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)
        self.assertEqual(order.shipping_cost, Decimal('15.90'))
        self.assertEqual(order.shipping_service, 'PAC')
        self.assertEqual(order.total, Decimal('115.80'))
        self.assertEqual(order.payment_method, Order.PAYMENT_WHATSAPP)
        self.assertEqual(order.status, Order.STATUS_AWAITING_CONTACT)
        self.assertFalse(cart.items.exists())

    def test_checkout_accepts_a_selected_free_shipping_option(self):
        product = Product.objects.create(
            name='Produto com frete gratis',
            category=self.category,
            price='59.90',
            stock=2,
            status=Product.STATUS_AVAILABLE,
        )
        cart = Cart.objects.create(user=self.owner)
        CartItem.objects.create(cart=cart, product=product, quantity=1)
        self.client.login(username='cliente@example.com', password='SenhaForte123!')
        self.client.get(reverse('orders:checkout'))
        session = self.client.session
        session['shipping_cost'] = '0.00'
        session['shipping_service'] = 'Frete gratis'
        session['shipping_cep'] = '01001000'
        session['shipping_cart_signature'] = cart_signature(cart)
        session.save()

        response = self.client.post(reverse('orders:checkout'), data={
            'checkout_token': self.client.session[CHECKOUT_TOKEN_SESSION_KEY],
            'customer_name': 'Cliente Teste',
            'customer_email': 'cliente@example.com',
            'customer_whatsapp': '11987654321',
            'address': 'Rua Teste',
            'address_number': '123',
            'neighborhood': 'Centro',
            'city': 'Sao Paulo',
            'state': 'SP',
            'cep': '01001-000',
            'shipping_method': 'delivery',
            'customer_notes': '',
        })

        order = Order.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(order.shipping_cost, Decimal('0.00'))
        self.assertEqual(order.shipping_service, 'Frete gratis')

    @override_settings(WHATSAPP_CHECKOUT_ONLY=False)
    def test_disabling_whatsapp_mode_restores_the_gateway_checkout(self):
        product = Product.objects.create(
            name='Produto gateway',
            category=self.category,
            price='89.90',
            stock=2,
            status=Product.STATUS_AVAILABLE,
        )
        cart = Cart.objects.create(user=self.owner)
        CartItem.objects.create(cart=cart, product=product, quantity=1)
        self.client.login(username='cliente@example.com', password='SenhaForte123!')

        checkout_page = self.client.get(reverse('orders:checkout'))
        self.assertContains(checkout_page, 'Forma de pagamento')
        self.assertContains(checkout_page, 'value="pix"')

        response = self.client.post(reverse('orders:checkout'), data={
            'checkout_token': self.client.session[CHECKOUT_TOKEN_SESSION_KEY],
            'customer_name': 'Cliente Teste',
            'customer_email': 'cliente@example.com',
            'customer_whatsapp': '11987654321',
            'shipping_method': 'pickup',
            'payment_method': Order.PAYMENT_PIX,
            'customer_notes': '',
        })

        order = Order.objects.get()
        self.assertRedirects(
            response,
            reverse('orders:success', args=[order.order_number]),
            fetch_redirect_response=False,
        )
        self.assertEqual(order.payment_method, Order.PAYMENT_PIX)
        self.assertEqual(order.status, Order.STATUS_AWAITING_PAYMENT)
        self.assertFalse(cart.items.exists())

    def test_checkout_form_normalizes_delivery_contact_fields(self):
        form = CheckoutForm(data={
            'checkout_token': 'test-token',
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
            'shipping_method': 'delivery',
            'customer_notes': '',
        })

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['customer_email'], 'cliente@example.com')
        self.assertEqual(form.cleaned_data['customer_whatsapp'], '11987654321')
        self.assertEqual(form.cleaned_data['cep'], '01001-000')
        self.assertEqual(form.cleaned_data['state'], 'SP')

    def test_pickup_checkout_does_not_require_address_or_cep(self):
        form = CheckoutForm(data={
            'checkout_token': 'test-token',
            'customer_name': 'Cliente Teste',
            'customer_email': 'cliente@example.com',
            'customer_whatsapp': '11987654321',
            'shipping_method': 'pickup',
            'address': '',
            'address_number': '',
            'address_complement': '',
            'neighborhood': '',
            'city': '',
            'state': '',
            'cep': '',
            'customer_notes': '',
        })

        self.assertTrue(form.is_valid(), form.errors)

    def test_delivery_checkout_rejects_missing_or_stale_shipping(self):
        product = Product.objects.create(
            name='Produto com frete',
            category=self.category,
            price='99.90',
            stock=2,
            status=Product.STATUS_AVAILABLE,
        )
        cart = Cart.objects.create(user=self.owner)
        CartItem.objects.create(cart=cart, product=product, quantity=1)
        self.client.login(username='cliente@example.com', password='SenhaForte123!')
        self.client.get(reverse('orders:checkout'))

        response = self.client.post(reverse('orders:checkout'), data={
            'checkout_token': self.client.session[CHECKOUT_TOKEN_SESSION_KEY],
            'customer_name': 'Cliente Teste',
            'customer_email': 'cliente@example.com',
            'customer_whatsapp': '11987654321',
            'shipping_method': 'delivery',
            'address': 'Rua Teste',
            'address_number': '123',
            'address_complement': '',
            'neighborhood': 'Centro',
            'city': 'Sao Paulo',
            'state': 'SP',
            'cep': '01001-000',
            'customer_notes': '',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Calcule e selecione o frete')
        self.assertFalse(Order.objects.exists())
        self.assertTrue(cart.items.exists())

    def test_checkout_is_idempotent_for_the_same_token(self):
        product = Product.objects.create(
            name='Produto idempotente',
            category=self.category,
            price='79.90',
            stock=3,
            status=Product.STATUS_AVAILABLE,
        )
        cart = Cart.objects.create(user=self.owner)
        CartItem.objects.create(cart=cart, product=product, quantity=1)
        self.client.login(username='cliente@example.com', password='SenhaForte123!')
        self.client.get(reverse('orders:checkout'))
        token = self.client.session[CHECKOUT_TOKEN_SESSION_KEY]
        payload = {
            'checkout_token': token,
            'customer_name': 'Cliente Teste',
            'customer_email': 'cliente@example.com',
            'customer_whatsapp': '11987654321',
            'shipping_method': 'pickup',
            'customer_notes': '',
        }

        first = self.client.post(reverse('orders:checkout'), data=payload)
        session = self.client.session
        session[CHECKOUT_TOKEN_SESSION_KEY] = token
        session.save()
        second = self.client.post(reverse('orders:checkout'), data=payload)

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(Order.objects.count(), 1)

    @override_settings(STORE_WHATSAPP='5535999073391')
    def test_whatsapp_message_uses_server_side_order_snapshot(self):
        product = Product.objects.create(
            name='Produto seguro',
            category=self.category,
            price='109.90',
            stock=5,
            status=Product.STATUS_AVAILABLE,
        )
        order = self.create_order()
        order.payment_method = Order.PAYMENT_WHATSAPP
        order.status = Order.STATUS_AWAITING_CONTACT
        order.save(update_fields=['payment_method', 'status'])
        order.items.create(
            product=product,
            product_name=product.name,
            unit_price=Decimal('109.90'),
            quantity=2,
            is_pre_order=False,
        )

        url = build_order_whatsapp_url(order)

        self.assertTrue(url.startswith('https://wa.me/5535999073391?'))
        self.assertIn('Produto+seguro', url)
        self.assertIn('219%2C80', url)
        self.assertIn('aguarda+confirma', url)

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

    def test_confirm_order_payment_refuses_insufficient_stock(self):
        product = Product.objects.create(
            name='Produto sem saldo',
            category=self.category,
            price='99.90',
            stock=1,
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

        with self.assertRaises(InsufficientStockError):
            confirm_order_payment(order)

        order.refresh_from_db()
        product.refresh_from_db()
        self.assertNotEqual(order.payment_status, 'confirmed')
        self.assertEqual(product.stock, 1)
