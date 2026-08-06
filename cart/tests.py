from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from unittest.mock import patch

from accounts.models import User
from products.models import Category, Product
from .models import Cart, CartItem
from .utils import CART_SESSION_TOKEN_KEY


@override_settings(
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
    FERNET_KEYS=['y_0UztNJ7Z1bTin2n33g6tE2x3BNbpBgiiSy8WEPOXA='],
)
class CartValidationTests(TestCase):
    def setUp(self):
        self.category, _ = Category.objects.get_or_create(
            slug='perfumes',
            defaults={'name': 'Perfumes'},
        )
        self.product = Product.objects.create(
            name='Produto Estoque',
            category=self.category,
            price='99.90',
            stock=2,
            status=Product.STATUS_AVAILABLE,
        )

    def test_cart_add_rejects_quantity_above_stock(self):
        response = self.client.post(
            reverse('cart:add', args=[self.product.pk]),
            {'quantity': '3'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(CartItem.objects.exists())

    def test_cart_add_rejects_invalid_quantity(self):
        response = self.client.post(
            reverse('cart:add', args=[self.product.pk]),
            {'quantity': 'abc'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(CartItem.objects.exists())

    def test_cacheable_catalog_omits_csrf_token_from_product_cards(self):
        response = self.client.get(reverse('products:list'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'csrfmiddlewaretoken')
        self.assertEqual(
            response['Cache-Control'],
            'public, s-maxage=60, stale-while-revalidate=300',
        )

    def test_quick_add_can_bootstrap_csrf_from_cacheable_catalog(self):
        csrf_client = Client(enforce_csrf_checks=True)
        token_response = csrf_client.get(reverse('cart:csrf'))

        self.assertEqual(token_response.status_code, 200)
        self.assertIn('csrftoken', token_response.cookies)
        csrf_token = token_response.json()['csrf_token']

        add_response = csrf_client.post(
            reverse('cart:add', args=[self.product.pk]),
            {'quantity': '1'},
            HTTP_X_CSRFTOKEN=csrf_token,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(add_response.status_code, 200)
        self.assertTrue(add_response.json()['success'])

    def test_cart_add_keeps_database_work_bounded_and_reports_duration(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.post(
                reverse('cart:add', args=[self.product.pk]),
                {'quantity': '1'},
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 12)
        self.assertTrue(any('SUM(' in query['sql'] for query in queries))
        self.assertRegex(response['Server-Timing'], r'^cart;dur=\d+(?:\.\d+)?$')

    def test_select_shipping_requires_calculated_option(self):
        self.client.post(
            reverse('cart:add', args=[self.product.pk]),
            {'quantity': '1'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        shipping_result = {
            'success': True,
            'cep': '01001000',
            'options': [{
                'service': 'pac',
                'label': 'PAC',
                'price': 15.90,
                'days': 5,
                'carrier': 'Correios',
            }],
        }
        with patch('cart.views.calculate_shipping', return_value=shipping_result):
            shipping_response = self.client.get(reverse('cart:shipping'), {'cep': '01001000'})
        self.assertEqual(shipping_response.status_code, 200)
        option = shipping_response.json()['options'][0]

        invalid_response = self.client.post(
            reverse('cart:select_shipping'),
            {'service': option['service'], 'price': '0.01'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(invalid_response.status_code, 400)

        valid_response = self.client.post(
            reverse('cart:select_shipping'),
            {'service': option['service'], 'price': str(option['price'])},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(valid_response.status_code, 200)
        self.assertEqual(self.client.session['shipping_cost'], str(option['price']))

    @override_settings(SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies')
    def test_anonymous_cart_survives_signed_cookie_session_changes(self):
        response = self.client.post(
            reverse('cart:add', args=[self.product.pk]),
            {'quantity': '1'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)

        session = self.client.session
        token = session[CART_SESSION_TOKEN_KEY]
        session['unrelated_session_change'] = 'keeps-cart-stable'
        session.save()

        detail = self.client.get(reverse('cart:detail'))
        self.assertContains(detail, self.product.name)
        self.assertEqual(
            CartItem.objects.get(cart__session_key=token, product=self.product).quantity,
            1,
        )

    def test_anonymous_carts_do_not_leak_between_clients(self):
        self.client.post(
            reverse('cart:add', args=[self.product.pk]),
            {'quantity': '1'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        other_client = Client()

        response = other_client.get(reverse('cart:detail'))

        self.assertNotContains(response, self.product.name)
        self.assertEqual(Cart.objects.filter(user=None).count(), 2)

    def test_anonymous_cart_merges_into_authenticated_cart(self):
        self.client.post(
            reverse('cart:add', args=[self.product.pk]),
            {'quantity': '1'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        user = User.objects.create_user(
            username='cliente@example.com',
            email='cliente@example.com',
            password='SenhaForte123!',
            full_name='Cliente Teste',
            whatsapp='11987654321',
        )

        self.client.login(username=user.username, password='SenhaForte123!')
        response = self.client.get(reverse('cart:detail'))

        self.assertContains(response, self.product.name)
        self.assertEqual(CartItem.objects.get(cart__user=user).quantity, 1)
        self.assertFalse(Cart.objects.filter(user=None, items__isnull=False).exists())

    def test_pre_order_accepts_quantity_when_physical_stock_is_zero(self):
        pre_order = Product.objects.create(
            name='Produto sob encomenda',
            category=self.category,
            price='129.90',
            stock=0,
            status=Product.STATUS_PRE_ORDER,
            is_pre_order=True,
        )

        response = self.client.post(
            reverse('cart:add', args=[pre_order.pk]),
            {'quantity': '5'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(CartItem.objects.get(product=pre_order).quantity, 5)

    def test_cart_mutation_invalidates_selected_shipping(self):
        self.client.post(
            reverse('cart:add', args=[self.product.pk]),
            {'quantity': '1'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        item = CartItem.objects.get(product=self.product)
        session = self.client.session
        session['shipping_cost'] = '15.90'
        session['shipping_service'] = 'PAC'
        session['shipping_cart_signature'] = 'old-signature'
        session.save()

        response = self.client.post(
            reverse('cart:update', args=[item.pk]),
            {'quantity': '2'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('shipping_cost', self.client.session)
        self.assertNotIn('shipping_cart_signature', self.client.session)

    def test_shipping_selection_rejects_stale_cart_signature(self):
        self.client.post(
            reverse('cart:add', args=[self.product.pk]),
            {'quantity': '1'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        session = self.client.session
        session['shipping_options'] = [{
            'service': 'pac',
            'label': 'PAC',
            'price': 15.90,
            'carrier': 'Correios',
        }]
        session['shipping_cart_signature'] = 'stale'
        session.save()

        response = self.client.post(
            reverse('cart:select_shipping'),
            {'service': 'pac', 'price': '15.90'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 409)
        self.assertNotIn('shipping_options', self.client.session)

    def test_product_page_can_quote_shipping_without_creating_an_empty_cart(self):
        shipping_result = {
            'success': True,
            'cep': '01001000',
            'options': [],
            'note': 'Estimativa.',
        }
        with patch('cart.views.calculate_shipping', return_value=shipping_result) as calculate_mock:
            response = self.client.get(
                reverse('cart:shipping'),
                {'cep': '01001000', 'product_id': self.product.pk},
            )

        self.assertEqual(response.status_code, 200)
        calculate_mock.assert_called_once_with('01001000', product=self.product)
        self.assertFalse(Cart.objects.exists())

    def test_cart_marks_item_unavailable_when_stock_drops(self):
        self.client.post(
            reverse('cart:add', args=[self.product.pk]),
            {'quantity': '2'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.product.stock = 1
        self.product.save(update_fields=['stock'])

        response = self.client.get(reverse('cart:detail'))

        self.assertTrue(response.context['cart'].has_unavailable_items)
        item = CartItem.objects.get(product=self.product)
        update_response = self.client.post(
            reverse('cart:update', args=[item.pk]),
            {'quantity': '1'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(update_response.status_code, 200)
        refreshed = self.client.get(reverse('cart:detail'))
        self.assertFalse(refreshed.context['cart'].has_unavailable_items)
