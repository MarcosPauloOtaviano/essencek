from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from orders.models import Order
from products.models import Brand, Category, HomeCollection, Product
from .services import get_dashboard_summary, get_reports_data


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}},
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

    def test_home_collection_management_pages_load(self):
        collection = HomeCollection.objects.create(
            key='colecao-teste',
            title='Colecao teste',
            route_slug='colecao-teste',
            kind=HomeCollection.KIND_FEATURED,
        )

        list_response = self.client.get(reverse('dashboard:home_collections'))
        edit_response = self.client.get(reverse('dashboard:home_collection_edit', args=[collection.pk]))

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, 'Colecao teste')
        self.assertEqual(edit_response.status_code, 200)
        self.assertContains(edit_response, 'name="route_slug"')


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}},
)
class DashboardPaymentReportTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='relatorio@example.com',
            email='relatorio@example.com',
            password='SenhaForte123!',
            full_name='Admin Relatorio',
            is_staff=True,
        )
        self.customer = User.objects.create_user(
            username='cliente-relatorio@example.com',
            email='cliente-relatorio@example.com',
            password='SenhaForte123!',
            full_name='Cliente Relatorio',
        )
        self.category = Category.objects.create(name='Categoria', slug='categoria-relatorio')
        self.product = Product.objects.create(
            name='Produto pago',
            category=self.category,
            price=Decimal('50.00'),
            cost_price=Decimal('20.00'),
            stock=10,
            status=Product.STATUS_AVAILABLE,
        )

    def create_order(self, *, total, payment_status, status, confirmed_at=None):
        order = Order.objects.create(
            customer=self.customer,
            customer_name='Cliente Relatorio',
            customer_email='cliente-relatorio@example.com',
            customer_whatsapp='11999999999',
            address='Rua Teste',
            address_number='10',
            city='Sao Paulo',
            state='SP',
            cep='01001-000',
            subtotal=total,
            total=total,
            payment_method=Order.PAYMENT_PIX,
            payment_status=payment_status,
            status=status,
            payment_confirmed_at=confirmed_at,
        )
        return order

    def test_financial_reports_use_payment_confirmation_as_source_of_truth(self):
        now = timezone.now()
        paid = self.create_order(
            total=Decimal('100.00'),
            payment_status=Order.PAYMENT_STATUS_CONFIRMED,
            status=Order.STATUS_AWAITING_PAYMENT,
            confirmed_at=now,
        )
        paid.items.create(
            product=self.product,
            product_name=self.product.name,
            unit_price=Decimal('50.00'),
            quantity=2,
        )
        unpaid = self.create_order(
            total=Decimal('300.00'),
            payment_status=Order.PAYMENT_STATUS_PENDING,
            status=Order.STATUS_SHIPPED,
        )
        unpaid.items.create(
            product=self.product,
            product_name='Produto ainda não pago',
            unit_price=Decimal('300.00'),
            quantity=1,
        )
        self.create_order(
            total=Decimal('50.00'),
            payment_status=Order.PAYMENT_STATUS_REFUNDED,
            status=Order.STATUS_CANCELLED,
            confirmed_at=now,
        )

        report = get_reports_data(now)
        summary = get_dashboard_summary(now)

        self.assertEqual(report['revenue_month'], Decimal('100.00'))
        self.assertEqual(report['paid_orders_month'], 1)
        self.assertEqual(report['pending_orders'], 1)
        self.assertEqual(report['pending_amount'], Decimal('300.00'))
        self.assertEqual(report['refunded_count'], 1)
        self.assertEqual(report['refunded_amount'], Decimal('50.00'))
        self.assertEqual(list(report['top_products'])[0]['product_name'], 'Produto pago')
        self.assertEqual(summary['monthly_revenue'], Decimal('100.00'))
        self.assertEqual(summary['awaiting_payment'], 1)

    def test_report_page_explains_automatic_status_and_shows_payment_labels(self):
        self.create_order(
            total=Decimal('100.00'),
            payment_status=Order.PAYMENT_STATUS_CONFIRMED,
            status=Order.STATUS_PAYMENT_CONFIRMED,
            confirmed_at=timezone.now(),
        )
        self.client.login(username='relatorio@example.com', password='SenhaForte123!')

        response = self.client.get(reverse('dashboard:reports'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Receita confirmada no mês')
        self.assertContains(response, 'atualizados automaticamente')
        self.assertContains(response, '>Pago<', html=False)
