import shutil
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.datastructures import MultiValueDict
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from accounts.models import User
from .forms import BrandForm, ProductForm
from .gtin_service import lookup_gtin, lookup_product_identifier, normalize_gtin
from .image_downloader import download_and_process_image
from .models import Brand, Category, HomeCollection, Product, ProductImage, ProductVariant
from .services import active_category_queryset, build_filter_tree


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

    def test_dashboard_product_add_accepts_long_product_name(self):
        User.objects.create_user(
            username='admin@example.com',
            email='admin@example.com',
            password='SenhaForte123!',
            full_name='Admin Teste',
            is_staff=True,
        )
        self.client.login(username='admin@example.com', password='SenhaForte123!')
        data = self.product_form_data()
        data['name'] = (
            'Perfume Arabe Masculino Importado Premium Fragrancia Intensa '
            'Edicao Especial Estoque Limitado'
        )

        response = self.client.post(reverse('dashboard:product_add'), data=data)

        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(name=data['name'])
        self.assertLessEqual(len(product.slug), Product._meta.get_field('slug').max_length)

    def test_product_form_rejects_invalid_sale_price(self):
        data = self.product_form_data()
        data.update({
            'is_on_sale': 'on',
            'sale_price': '250.00',
        })

        form = ProductForm(data=data)

        self.assertFalse(form.is_valid())
        self.assertIn('sale_price', form.errors)

    def test_product_form_saves_long_name_with_truncated_unique_slug(self):
        long_name = (
            'Perfume Arabe Masculino Importado Premium Fragrancia Intensa '
            'Edicao Especial Estoque Limitado'
        )
        first_data = self.product_form_data()
        first_data['name'] = long_name

        first_form = ProductForm(data=first_data)

        self.assertTrue(first_form.is_valid(), first_form.errors)
        first_product = first_form.save()
        self.assertLessEqual(len(first_product.slug), Product._meta.get_field('slug').max_length)

        second_data = self.product_form_data()
        second_data['name'] = long_name
        second_data['gtin'] = '7500435135030'

        second_form = ProductForm(data=second_data)

        self.assertTrue(second_form.is_valid(), second_form.errors)
        second_product = second_form.save()
        self.assertLessEqual(len(second_product.slug), Product._meta.get_field('slug').max_length)
        self.assertNotEqual(second_product.slug, first_product.slug)

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

    def test_product_main_image_uses_prefetched_images_without_extra_queries(self):
        product = Product.objects.create(
            name='Produto com fotos prefetch',
            category=self.category,
            price='99.90',
            stock=3,
            status=Product.STATUS_AVAILABLE,
        )
        secondary = ProductImage.objects.create(
            product=product,
            image=make_image_upload('secundaria.jpg'),
            is_main=False,
            order=2,
        )
        main = ProductImage.objects.create(
            product=product,
            image=make_image_upload('principal.jpg'),
            is_main=True,
            order=1,
        )

        product = Product.objects.prefetch_related('images').get(pk=product.pk)

        with self.assertNumQueries(0):
            self.assertEqual(product.main_image.pk, main.pk)
            self.assertNotEqual(product.main_image.pk, secondary.pk)


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
)
class CatalogNavigationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.perfume_category = Category.objects.create(
            name='Perfume Arabe Feminino',
            slug='perfume-arabe-feminino',
        )
        self.kbeauty_category = Category.objects.create(
            name='Skincare Coreano',
            slug='Skincare-coreano',
        )
        self.niche_category = Category.objects.create(
            name='Perfumes de Nicho',
            slug='perfumes-importados-nicho',
        )
        self.japanese_beauty_category = Category.objects.create(
            name='Beleza japonesa',
            slug='beleza-japonesa-tratamento-cabelos',
        )
        self.empty_legacy_category = Category.objects.create(
            name='Perfumes legado vazio',
            slug='perfumes',
        )
        self.empty_decanter_category = Category.objects.create(
            name='Decanter 5 ml',
            slug='Perfume-fracionado-decanter5ml',
        )
        self.empty_decanter_ten_category = Category.objects.create(
            name='Decanter 10 ml',
            slug='Perfume-fracionado-decanter10ml',
        )
        self.empty_supplements_category = Category.objects.create(
            name='Suplementos',
            slug='suplementos-saude-bem-estar',
        )
        self.empty_electronics_category = Category.objects.create(
            name='Eletronicos vazio',
            slug='eletronicos-tecnologia',
        )

        self.perfume = Product.objects.create(
            name='Perfume Real',
            category=self.perfume_category,
            price='200.00',
            sale_price='150.00',
            stock=3,
            status=Product.STATUS_AVAILABLE,
            is_on_sale=True,
            is_featured=True,
        )
        self.kbeauty = Product.objects.create(
            name='K Beauty Real',
            category=self.kbeauty_category,
            price='90.00',
            stock=2,
            status=Product.STATUS_AVAILABLE,
        )
        self.niche = Product.objects.create(
            name='Perfume de Nicho Real',
            category=self.niche_category,
            price='350.00',
            stock=2,
            status=Product.STATUS_AVAILABLE,
        )
        self.japanese_beauty = Product.objects.create(
            name='Beleza Japonesa Real',
            category=self.japanese_beauty_category,
            price='95.00',
            stock=2,
            status=Product.STATUS_AVAILABLE,
        )
        self.invalid_sale = Product.objects.create(
            name='Promocao invalida',
            category=self.perfume_category,
            price='100.00',
            sale_price='130.00',
            stock=2,
            status=Product.STATUS_AVAILABLE,
            is_on_sale=True,
        )

        HomeCollection.objects.all().delete()
        self.offers_collection = HomeCollection.objects.create(
            key='ofertas', title='Ofertas', route_slug='ofertas', kind=HomeCollection.KIND_OFFERS, order=10,
        )
        self.niche_collection = HomeCollection.objects.create(
            key='perfumes-de-nicho', title='Perfumes de Nicho', route_slug='perfumes-de-nicho',
            kind=HomeCollection.KIND_CATEGORY, order=20,
        )
        self.niche_collection.categories.add(self.niche_category)
        self.korean_collection = HomeCollection.objects.create(
            key='beleza-coreana', title='Beleza Coreana', route_slug='beleza-coreana',
            kind=HomeCollection.KIND_CATEGORY, order=30,
        )
        self.korean_collection.categories.add(self.kbeauty_category)
        self.decanter_collection = HomeCollection.objects.create(
            key='decanter', title='Decanter', route_slug='decanter', kind=HomeCollection.KIND_CATEGORY, order=40,
        )
        self.decanter_five_collection = HomeCollection.objects.create(
            key='decanter-5ml', title='Decanter 5 ml', route_slug='decanter-5ml',
            kind=HomeCollection.KIND_CATEGORY, parent=self.decanter_collection,
            is_home_visible=False, order=41,
        )
        self.decanter_five_collection.categories.add(self.empty_decanter_category)
        self.decanter_ten_collection = HomeCollection.objects.create(
            key='decanter-10ml', title='Decanter 10 ml', route_slug='decanter-10ml',
            kind=HomeCollection.KIND_CATEGORY, parent=self.decanter_collection,
            is_home_visible=False, order=42,
        )
        self.decanter_ten_collection.categories.add(self.empty_decanter_ten_category)
        self.supplements_collection = HomeCollection.objects.create(
            key='suplementos', title='Suplementos', route_slug='suplementos',
            kind=HomeCollection.KIND_CATEGORY, order=50,
        )
        self.supplements_collection.categories.add(self.empty_supplements_category)
        HomeCollection.objects.create(
            key='destaques', title='Destaques', route_slug='destaques',
            kind=HomeCollection.KIND_FEATURED, order=60,
        )
        HomeCollection.objects.create(
            key='pronta-entrega', title='Pronta Entrega', route_slug='pronta-entrega',
            kind=HomeCollection.KIND_AVAILABLE, order=70,
        )

    def test_home_shows_the_seven_configured_collections_including_empty_ones(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        for collection in (
            self.offers_collection, self.niche_collection, self.korean_collection,
            self.decanter_collection, self.supplements_collection,
        ):
            self.assertContains(response, collection.get_absolute_url())
            self.assertContains(response, collection.title)
        self.assertContains(response, '/categoria/destaques/')
        self.assertContains(response, '/categoria/pronta-entrega/')
        self.assertContains(response, 'Catalogo em preparacao')
        self.assertNotContains(response, 'ELETRO')

    def test_collection_routes_use_only_the_configured_real_categories(self):
        niche_response = self.client.get(reverse('category_landing', args=['perfumes-de-nicho']))
        korean_response = self.client.get(reverse('category_landing', args=['beleza-coreana']))

        self.assertEqual(niche_response.status_code, 200)
        self.assertContains(niche_response, 'Perfume de Nicho Real')
        self.assertNotContains(niche_response, 'Perfume Real')
        self.assertNotContains(niche_response, 'K Beauty Real')

        self.assertEqual(korean_response.status_code, 200)
        self.assertContains(korean_response, 'K Beauty Real')
        self.assertNotContains(korean_response, 'Beleza Japonesa Real')
        self.assertNotContains(korean_response, 'Perfume Real')

    def test_decanter_has_two_valid_subcollections_even_before_product_registration(self):
        response = self.client.get(reverse('category_landing', args=['decanter']))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Decanter 5 ml')
        self.assertContains(response, 'Decanter 10 ml')
        self.assertContains(response, 'Decanter esta em preparacao')
        self.assertContains(response, reverse('category_landing', args=['decanter-5ml']))
        self.assertContains(response, reverse('category_landing', args=['decanter-10ml']))

    def test_legacy_category_routes_canonicalize_without_losing_the_catalog(self):
        legacy_query_response = self.client.get(
            reverse('products:list'),
            {'category': 'perfume-arabe-feminino'},
        )
        category_route_response = self.client.get(
            reverse('category_landing', args=['Skincare-coreano']),
        )

        self.assertContains(legacy_query_response, 'Perfume Real')
        self.assertNotContains(legacy_query_response, 'K Beauty Real')
        self.assertEqual(category_route_response.status_code, 301)
        self.assertEqual(category_route_response['Location'], self.korean_collection.get_absolute_url())

    def test_unknown_collection_route_returns_not_found(self):
        response = self.client.get(reverse('category_landing', args=['colecao-inexistente']))

        self.assertEqual(response.status_code, 404)

    def test_catalog_uses_promotional_price_when_sorting_by_price(self):
        Product.objects.create(
            name='Produto com preco promocional menor',
            category=self.perfume_category,
            price='300.00',
            sale_price='50.00',
            stock=2,
            status=Product.STATUS_AVAILABLE,
            is_on_sale=True,
        )

        response = self.client.get(reverse('products:list'), {'sort': 'price_asc'})
        product_names = [product.name for product in response.context['products'].object_list]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(product_names[0], 'Produto com preco promocional menor')

    def test_offer_route_only_returns_valid_public_sales(self):
        response = self.client.get(reverse('offers'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Perfume Real')
        self.assertNotContains(response, 'Promocao invalida')
        self.assertNotContains(response, 'K Beauty Real')

    def test_text_search_does_not_match_every_product_via_empty_gtin(self):
        response = self.client.get(reverse('products:list'), {'q': 'produto inexistente'})

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Perfume Real')
        self.assertNotContains(response, 'K Beauty Real')

    def test_filter_tree_query_count_does_not_grow_with_categories(self):
        extra_parent = Category.objects.create(name='Maquiagem', slug='maquiagem')
        extra_child = Category.objects.create(
            name='Lábios',
            slug='labios',
            parent=extra_parent,
        )
        Product.objects.create(
            name='Batom teste',
            category=extra_child,
            price='50.00',
            stock=1,
            status=Product.STATUS_AVAILABLE,
        )
        categories = list(active_category_queryset())

        with self.assertNumQueries(1):
            tree, _, _ = build_filter_tree(categories, '', '', '', '')

        self.assertGreaterEqual(len(tree), 2)


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


class ProductAvailabilityTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Decanters', slug='decanters-teste')

    def test_fractioned_product_requires_an_available_variant(self):
        product = Product.objects.create(
            name='Perfume fracionado',
            category=self.category,
            price='50.00',
            stock=0,
            status=Product.STATUS_AVAILABLE,
            is_fractioned=True,
            has_variants=True,
        )
        ProductVariant.objects.create(
            product=product,
            name='5ml',
            price='50.00',
            stock=0,
            is_active=True,
        )
        self.assertFalse(product.can_add_to_cart())

        ProductVariant.objects.create(
            product=product,
            name='10ml',
            price='90.00',
            stock=2,
            is_active=True,
        )

        self.assertTrue(product.can_add_to_cart())

    def test_product_detail_selects_first_variant_with_stock(self):
        product = Product.objects.create(
            name='Perfume com volumes',
            category=self.category,
            price='50.00',
            stock=2,
            status=Product.STATUS_AVAILABLE,
            is_fractioned=True,
            has_variants=True,
        )
        ProductVariant.objects.create(
            product=product,
            name='5ml',
            price='50.00',
            stock=0,
            is_active=True,
            order=0,
        )
        available = ProductVariant.objects.create(
            product=product,
            name='10ml',
            price='90.00',
            stock=2,
            is_active=True,
            order=1,
        )

        response = self.client.get(reverse('products:detail', args=[product.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['first_variant'], available)

    def test_fractioned_pre_order_requires_an_active_variant_but_not_stock(self):
        product = Product.objects.create(
            name='Encomenda fracionada',
            category=self.category,
            price='50.00',
            stock=0,
            status=Product.STATUS_PRE_ORDER,
            is_pre_order=True,
            is_fractioned=True,
            has_variants=True,
        )

        self.assertFalse(product.can_add_to_cart())
        ProductVariant.objects.create(
            product=product,
            name='5ml',
            price='50.00',
            stock=0,
            is_active=True,
        )

        self.assertTrue(product.can_add_to_cart())


class ProductImageDownloadSecurityTests(TestCase):
    def test_image_downloader_blocks_loopback_destination(self):
        result = download_and_process_image('http://127.0.0.1:8000/private-image')

        self.assertIsNone(result)

    @patch('products.image_downloader._is_public_image_url', return_value=True)
    @patch('products.image_downloader.requests.get')
    def test_image_downloader_rejects_invalid_content_length(self, get_mock, _public_mock):
        response = MagicMock()
        response.is_redirect = False
        response.is_permanent_redirect = False
        response.headers = {
            'Content-Type': 'image/jpeg',
            'Content-Length': 'not-a-number',
        }
        get_mock.return_value = response

        result = download_and_process_image('https://images.example/product.jpg')

        self.assertIsNone(result)
        response.close.assert_called_once()
