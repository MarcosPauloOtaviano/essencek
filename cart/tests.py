from django.test import TestCase, override_settings
from django.urls import reverse

from products.models import Category, Product
from .models import CartItem


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
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

    def test_select_shipping_requires_calculated_option(self):
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
