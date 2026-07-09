import shutil
import tempfile
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.datastructures import MultiValueDict
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from accounts.models import User
from .forms import BrandForm, ProductForm
from .gtin_service import lookup_gtin, lookup_product_identifier, normalize_gtin
from .models import Brand, Category, Product, ProductImage


def make_image_upload(name='foto.jpg', size=(900, 700), color=(160, 90, 60)):
    image = Image.new('RGB', size, color)
    output = BytesIO()
    image.save(output, format='JPEG')
    return SimpleUploadedFile(name, output.getvalue(), content_type='image/jpeg')


class ProductLocalImageUploadTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.settings_override = override_settings(
            MEDIA_ROOT=self.media_root,
            STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)

        self.category, _ = Category.objects.get_or_create(
            slug='perfumes',
            defaults={'name': 'Perfumes'},
        )

    def product_form_data(self):
        return {
            'name': 'Perfume Teste',
            'brand': 'Marca',
            'category': str(self.category.pk),
            'short_description': '',
            'description': '',
            'price_usd': '38.61',
            'sale_price_usd': '',
            'cost_price_usd': '',
            'price': '199.90',
            'sale_price': '',
            'cost_price': '',
            'stock': '5',
            'status': Product.STATUS_AVAILABLE,
            'is_active': 'on',
            'weight': '0.300',
            'height': '10',
            'width': '10',
            'length': '10',
            'internal_notes': '',
        }

    def test_product_form_accepts_multiple_local_image_files(self):
        files = MultiValueDict({
            'images': [
                make_image_upload('foto-celular-1.jpg'),
                make_image_upload('foto-celular-2.jpg'),
            ]
        })

        form = ProductForm(data=self.product_form_data(), files=files)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(len(form.cleaned_data['images']), 2)

    def test_dashboard_product_add_saves_uploaded_phone_photo_locally(self):
        User.objects.create_user(
            username='admin@example.com',
            email='admin@example.com',
            password='SenhaForte123!',
            full_name='Admin Teste',
            is_staff=True,
        )
        self.client.login(username='admin@example.com', password='SenhaForte123!')

        response = self.client.post(reverse('dashboard:product_add'), data={
            **self.product_form_data(),
            'images': [make_image_upload('foto do celular.jpg', size=(2200, 1800))],
        })

        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(name='Perfume Teste')
        product_image = ProductImage.objects.get(product=product)
        saved_path = Path(settings.MEDIA_ROOT) / product_image.image.name

        self.assertTrue(saved_path.exists())
        self.assertTrue(product_image.image.name.startswith('products/perfume-teste/'))
        self.assertTrue(product_image.image.name.endswith('.jpg'))
        with Image.open(saved_path) as saved_image:
            self.assertEqual(saved_image.format, 'JPEG')
            self.assertLessEqual(max(saved_image.size), 1800)

    def test_product_form_rejects_invalid_sale_price(self):
        data = self.product_form_data()
        data.update({
            'is_on_sale': 'on',
            'sale_price': '250.00',
        })

        form = ProductForm(data=data)

        self.assertFalse(form.is_valid())
        self.assertIn('sale_price', form.errors)

    def test_dashboard_image_delete_requires_post(self):
        User.objects.create_user(
            username='admin@example.com',
            email='admin@example.com',
            password='SenhaForte123!',
            full_name='Admin Teste',
            is_staff=True,
        )
        self.client.login(username='admin@example.com', password='SenhaForte123!')
        product = Product.objects.create(
            name='Produto com foto',
            category=self.category,
            price='99.90',
            stock=3,
            status=Product.STATUS_AVAILABLE,
        )
        product_image = ProductImage.objects.create(product=product, image=make_image_upload())

        get_response = self.client.get(reverse('dashboard:image_delete', args=[product_image.pk]))
        self.assertEqual(get_response.status_code, 405)
        self.assertTrue(ProductImage.objects.filter(pk=product_image.pk).exists())

        post_response = self.client.post(reverse('dashboard:image_delete', args=[product_image.pk]))
        self.assertEqual(post_response.status_code, 302)
        self.assertFalse(ProductImage.objects.filter(pk=product_image.pk).exists())

    def test_product_uses_category_fallback_when_image_file_is_missing(self):
        product = Product.objects.create(
            name='Produto sem arquivo',
            category=self.category,
            price='99.90',
            stock=3,
            status=Product.STATUS_AVAILABLE,
        )
        product_image = ProductImage.objects.create(product=product, image=make_image_upload('existe.jpg'))
        saved_path = Path(settings.MEDIA_ROOT) / product_image.image.name
        saved_path.unlink()

        product = Product.objects.get(pk=product.pk)

        self.assertIn('/static/img/defaults/default-perfumes.jpg', product.display_image_url)
        self.assertIn('/static/img/defaults/default-perfumes.jpg', product.main_image.display_url)


class ProductGtinLookupTests(TestCase):
    def setUp(self):
        self.category, _ = Category.objects.get_or_create(
            slug='beleza-coreana',
            defaults={'name': 'Beleza Coreana'},
        )

    def test_normalize_gtin_keeps_only_digits(self):
        self.assertEqual(normalize_gtin(' 7500-435135030 '), '7500435135030')

    def test_lookup_gtin_finds_known_local_catalog_product(self):
        result = lookup_gtin('7500435135030')

        self.assertIsNotNone(result)
        self.assertFalse(result['existing'])
        self.assertEqual(result['gtin'], '7500435135030')
        self.assertIn('Old Spice', result['name'])
        self.assertEqual(result['brand'], 'Old Spice')
        self.assertNotIn('category_id', result)

    def test_lookup_gtin_returns_existing_product_before_catalog(self):
        product = Product.objects.create(
            name='Produto cadastrado',
            category=self.category,
            price='10.00',
            price_usd='2.00',
            stock=1,
            status=Product.STATUS_AVAILABLE,
            gtin='7500435135030',
        )

        result = lookup_gtin('7500435135030')

        self.assertTrue(result['existing'])
        self.assertEqual(result['product_id'], product.pk)
        self.assertEqual(result['name'], 'Produto cadastrado')

    def test_dashboard_gtin_endpoint_returns_known_product_data(self):
        User.objects.create_user(
            username='admin@example.com',
            email='admin@example.com',
            password='SenhaForte123!',
            full_name='Admin Teste',
            is_staff=True,
        )
        self.client.login(username='admin@example.com', password='SenhaForte123!')

        response = self.client.get(reverse('dashboard:gtin_lookup'), {'code': '7500435135030'})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['found'])
        self.assertEqual(payload['gtin'], '7500435135030')
        self.assertEqual(payload['brand'], 'Old Spice')

    def test_identifier_lookup_finds_existing_product_by_name(self):
        product = Product.objects.create(
            name='Good Girl Eau de Parfum',
            brand='Carolina Herrera',
            category=self.category,
            price='10.00',
            price_usd='2.00',
            stock=1,
            status=Product.STATUS_AVAILABLE,
        )

        result = lookup_product_identifier('good girl')

        self.assertTrue(result['existing'])
        self.assertEqual(result['product_id'], product.pk)

    def test_identifier_lookup_returns_draft_for_unsupported_numeric_code(self):
        result = lookup_product_identifier('123456789012345')

        self.assertIsNotNone(result)
        self.assertTrue(result['draft'])
        self.assertEqual(result['gtin'], '123456789012345')

    def test_product_form_normalizes_gtin(self):
        data = {
            'name': 'Produto GTIN',
            'brand': 'Marca',
            'category': str(self.category.pk),
            'short_description': '',
            'description': '',
            'price_usd': '',
            'sale_price_usd': '',
            'cost_price_usd': '',
            'price': '55.00',
            'sale_price': '',
            'cost_price': '',
            'stock': '2',
            'status': Product.STATUS_AVAILABLE,
            'is_active': 'on',
            'gtin': '7500-435135030',
            'weight': '0',
            'height': '0',
            'width': '0',
            'length': '0',
            'internal_notes': '',
        }

        form = ProductForm(data=data)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['gtin'], '7500435135030')


class BrandFormTests(TestCase):
    def test_brand_form_generates_slug_from_name(self):
        form = BrandForm(data={
            'name': 'Beauty of Joseon',
            'slug': '',
            'description': '',
            'is_active': 'on',
        })

        self.assertTrue(form.is_valid(), form.errors)
        brand = form.save()

        self.assertEqual(brand.slug, 'beauty-of-joseon')
        self.assertTrue(brand.is_active)

    def test_brand_form_generates_unique_slug_for_duplicate_name(self):
        Brand.objects.create(name='COSRX', slug='cosrx')

        form = BrandForm(data={
            'name': 'COSRX',
            'slug': '',
            'description': '',
            'is_active': 'on',
        })

        self.assertTrue(form.is_valid(), form.errors)
        brand = form.save()

        self.assertEqual(brand.slug, 'cosrx-1')

    def test_brand_form_rejects_non_image_logo(self):
        upload = SimpleUploadedFile('logo.txt', b'nao e imagem', content_type='text/plain')
        form = BrandForm(
            data={
                'name': 'Marca com logo ruim',
                'slug': '',
                'description': '',
                'is_active': 'on',
            },
            files={'logo': upload},
        )

        self.assertFalse(form.is_valid())
        self.assertIn('logo', form.errors)
