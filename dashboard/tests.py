from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from products.models import Brand, Category, Product


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
)
class DashboardBrandActionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='admin@example.com',
            email='admin@example.com',
            password='SenhaForte123!',
            full_name='Admin Teste',
            is_staff=True,
        )
        self.client.login(username='admin@example.com', password='SenhaForte123!')
        self.brand = Brand.objects.create(name='Marca Teste', slug='marca-teste')

    def test_brand_action_pages_load(self):
        list_response = self.client.get(reverse('dashboard:brands'))
        edit_response = self.client.get(reverse('dashboard:brand_edit', args=[self.brand.pk]))
        delete_response = self.client.get(reverse('dashboard:brand_delete', args=[self.brand.pk]))

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, reverse('dashboard:brand_edit', args=[self.brand.pk]))
        self.assertContains(list_response, reverse('dashboard:brand_delete', args=[self.brand.pk]))
        self.assertEqual(edit_response.status_code, 200)
        self.assertEqual(delete_response.status_code, 200)

    def test_brand_delete_removes_brand(self):
        response = self.client.post(reverse('dashboard:brand_delete', args=[self.brand.pk]))

        self.assertRedirects(response, reverse('dashboard:brands'), fetch_redirect_response=False)
        self.assertFalse(Brand.objects.filter(pk=self.brand.pk).exists())

    def test_brand_delete_preserves_linked_product_brand_text(self):
        category, _ = Category.objects.get_or_create(
            slug='perfumes',
            defaults={'name': 'Perfumes'},
        )
        product = Product.objects.create(
            name='Produto com marca',
            brand_fk=self.brand,
            category=category,
            price='99.90',
            stock=2,
            status=Product.STATUS_AVAILABLE,
        )

        response = self.client.post(reverse('dashboard:brand_delete', args=[self.brand.pk]))
        product.refresh_from_db()

        self.assertRedirects(response, reverse('dashboard:brands'), fetch_redirect_response=False)
        self.assertFalse(Brand.objects.filter(pk=self.brand.pk).exists())
        self.assertIsNone(product.brand_fk)
        self.assertEqual(product.brand, 'Marca Teste')
