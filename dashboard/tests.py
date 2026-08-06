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

    def test_category_form_exposes_parent_category_field(self):
        response = self.client.get(reverse('dashboard:category_add'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="parent"')

    def test_category_list_shows_parent_and_annotated_product_counts(self):
        parent = Category.objects.create(name='Perfumes', slug='perfumes')
        child = Category.objects.create(name='Perfume Arabe', slug='perfume-arabe', parent=parent)
        Product.objects.create(
            name='Produto ativo',
            category=child,
            price='99.90',
            stock=2,
            status=Product.STATUS_AVAILABLE,
            is_active=True,
        )
        Product.objects.create(
            name='Produto inativo',
            category=child,
            price='99.90',
            stock=0,
            status=Product.STATUS_OUT_OF_STOCK,
            is_active=False,
        )

        response = self.client.get(reverse('dashboard:categories'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Perfumes')
        self.assertContains(response, '2 <small>(1 ativos)</small>', html=True)
