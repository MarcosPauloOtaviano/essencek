from decimal import Decimal, ROUND_HALF_UP

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from core.models import ExchangeRate
from products.models import Brand, Category, Product, ProductVariant


def money(value):
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def usd_to_brl(value, rate):
    return (money(value) * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class Command(BaseCommand):
    help = 'Cria produtos demonstrativos da Essence K Importados sem duplicar dados.'

    brands = [
        'Carolina Herrera', 'Paco Rabanne', 'Dior', 'Lancôme', 'Yves Saint Laurent',
        'Chanel', 'Jean Paul Gaultier', 'Lattafa', 'Samsung', 'Apple', 'Anker',
        'Beauty of Joseon', 'COSRX', 'Laneige',
    ]

    sealed_perfumes = [
        ('Good Girl Eau de Parfum', 'Carolina Herrera', '92.00', 'available', True, False, None, 8, 'Perfume importado lacrado com perfil sofisticado e marcante.'),
        ('212 VIP Rosé', 'Carolina Herrera', '88.00', 'available', False, True, '78.00', 5, 'Perfume feminino elegante, fresco e moderno.'),
        ('Lady Million', 'Paco Rabanne', '85.00', 'low_stock', True, False, None, 2, 'Fragrância intensa, glamourosa e luminosa.'),
        ('Sauvage Eau de Parfum', 'Dior', '115.00', 'available', True, False, None, 6, 'Perfume masculino importado com presença premium.'),
        ('La Vie Est Belle', 'Lancôme', '98.00', 'available', False, True, '89.00', 4, 'Fragrância feminina doce, sofisticada e envolvente.'),
        ('Libre Eau de Parfum', 'Yves Saint Laurent', '105.00', 'low_stock', True, False, None, 2, 'Perfume moderno com assinatura floral e elegante.'),
        ('Coco Mademoiselle', 'Chanel', '125.00', 'available', False, False, None, 3, 'Clássico premium com toque elegante e atemporal.'),
        ('Scandal', 'Jean Paul Gaultier', '95.00', 'available', False, True, '84.00', 5, 'Perfume marcante, sensual e sofisticado.'),
    ]

    kbeauty = [
        ('Relief Sun Rice + Probiotics SPF50', 'Beauty of Joseon', '18.00', 'available', True, False, None, 18),
        ('Advanced Snail 96 Mucin Essence', 'COSRX', '22.00', 'available', True, True, '19.90', 14),
        ('Lip Sleeping Mask Berry', 'Laneige', '20.00', 'low_stock', False, False, None, 3),
        ('Glow Serum Propolis + Niacinamide', 'Beauty of Joseon', '17.00', 'available', False, True, '15.00', 12),
        ('Low pH Good Morning Gel Cleanser', 'COSRX', '14.00', 'available', False, False, None, 20),
    ]

    electronics = [
        ('Smartwatch Elegance Rose', 'Samsung', '45.00', 'available', True, False, None, 7),
        ('Fone Bluetooth Premium', 'Anker', '32.00', 'available', False, True, '28.00', 10),
        ('Carregador Turbo USB-C', 'Anker', '18.00', 'available', False, False, None, 15),
        ('iPhone Seminovo Selecionado', 'Apple', '420.00', 'low_stock', True, False, None, 2),
        ('Caixa de Som Portátil Mini', 'Anker', '38.00', 'available', False, False, None, 8),
    ]

    fractioned = [
        ('Good Girl - Fracionado', 'Carolina Herrera', [
            (10, '8.00', 10), (20, '15.00', 8), (30, '21.00', 6), (40, '28.00', 5),
            (50, '34.00', 4), (60, '40.00', 3), (70, '46.00', 2), (80, '52.00', 1),
        ]),
        ('212 VIP Rosé - Fracionado', 'Carolina Herrera', [
            (10, '7.50', 10), (20, '14.00', 7), (30, '20.00', 5), (50, '31.00', 4), (80, '48.00', 2),
        ]),
        ('Lady Million - Fracionado', 'Paco Rabanne', [
            (10, '8.00', 9), (20, '15.00', 7), (30, '22.00', 5), (50, '35.00', 3), (80, '54.00', 2),
        ]),
        ('Sauvage - Fracionado', 'Dior', [
            (10, '10.00', 10), (20, '18.00', 8), (30, '26.00', 6), (40, '34.00', 4), (50, '42.00', 3), (80, '62.00', 2),
        ]),
        ('La Vie Est Belle - Fracionado', 'Lancôme', [
            (10, '8.50', 9), (20, '16.00', 7), (30, '23.00', 5), (50, '36.00', 4), (80, '55.00', 2),
        ]),
        ('Libre - Fracionado', 'Yves Saint Laurent', [
            (10, '9.00', 8), (20, '17.00', 6), (30, '25.00', 5), (50, '39.00', 3), (80, '59.00', 2),
        ]),
        ('Scandal - Fracionado', 'Jean Paul Gaultier', [
            (10, '8.00', 8), (20, '15.50', 6), (30, '23.00', 5), (50, '36.00', 3), (80, '56.00', 2),
        ]),
    ]

    def handle(self, *args, **options):
        rate = ExchangeRate.get_usd_brl()
        stats = {
            'categories_created': 0,
            'brands_created': 0,
            'products_created': 0,
            'products_existing': 0,
            'variants_created': 0,
            'variants_existing': 0,
        }

        categories = self.ensure_categories(stats)
        brands = self.ensure_brands(stats)

        for index, data in enumerate(self.sealed_perfumes):
            self.upsert_product(categories['perfumes'], brands, rate, stats, data, order=index)

        for index, data in enumerate(self.kbeauty):
            self.upsert_product(
                categories['beleza-coreana'], brands, rate, stats, data,
                order=index, description='Produto de K-beauty selecionado para rotina de skincare premium.'
            )

        for index, data in enumerate(self.electronics):
            self.upsert_product(
                categories['eletronicos'], brands, rate, stats, data,
                order=index, description='Eletrônico importado selecionado com visual premium para o dia a dia.'
            )

        for index, (name, brand_name, variants) in enumerate(self.fractioned):
            product = self.upsert_fractioned_product(
                categories['perfumes-fracionados'], brands, rate, stats, name, brand_name, variants, order=index
            )
            self.upsert_variants(product, variants, rate, stats)

        self.stdout.write(self.style.SUCCESS('Produtos demonstrativos prontos.'))
        for key, value in stats.items():
            self.stdout.write(f'{key}: {value}')

    def ensure_categories(self, stats):
        perfumes, created = Category.objects.get_or_create(
            slug='perfumes',
            defaults={'name': 'Perfumes', 'order': 1, 'is_active': True},
        )
        if created:
            stats['categories_created'] += 1
        perfumes.name = 'Perfumes'
        perfumes.parent = None
        perfumes.is_active = True
        perfumes.order = 1
        perfumes.save()

        fracionados, created = Category.objects.get_or_create(
            slug='perfumes-fracionados',
            defaults={'name': 'Perfumes Fracionados', 'parent': perfumes, 'order': 2, 'is_active': True},
        )
        if created:
            stats['categories_created'] += 1
        fracionados.name = 'Perfumes Fracionados'
        fracionados.parent = perfumes
        fracionados.is_active = True
        fracionados.order = 2
        fracionados.save()

        beleza, created = Category.objects.get_or_create(
            slug='beleza-coreana',
            defaults={'name': 'Beleza Coreana', 'order': 3, 'is_active': True},
        )
        if created:
            stats['categories_created'] += 1
        beleza.name = 'Beleza Coreana'
        beleza.parent = None
        beleza.is_active = True
        beleza.order = 3
        beleza.save()

        eletronicos, created = Category.objects.get_or_create(
            slug='eletronicos',
            defaults={'name': 'Eletrônicos', 'order': 4, 'is_active': True},
        )
        if created:
            stats['categories_created'] += 1
        eletronicos.name = 'Eletrônicos'
        eletronicos.parent = None
        eletronicos.is_active = True
        eletronicos.order = 4
        eletronicos.save()

        return {
            'perfumes': perfumes,
            'perfumes-fracionados': fracionados,
            'beleza-coreana': beleza,
            'eletronicos': eletronicos,
        }

    def ensure_brands(self, stats):
        result = {}
        for name in self.brands:
            slug = slugify(name)
            brand, created = Brand.objects.get_or_create(
                slug=slug,
                defaults={'name': name, 'is_active': True},
            )
            if created:
                stats['brands_created'] += 1
            if brand.name != name or not brand.is_active:
                brand.name = name
                brand.is_active = True
                brand.save(update_fields=['name', 'is_active'])
            result[name] = brand
        return result

    def upsert_product(self, category, brands, rate, stats, data, order=0, description=''):
        if len(data) == 9:
            name, brand_name, price_usd, status, featured, on_sale, sale_price_usd, stock, short_description = data
        else:
            name, brand_name, price_usd, status, featured, on_sale, sale_price_usd, stock = data
            short_description = description or 'Produto demonstrativo selecionado para testar a loja.'
        price_usd = money(price_usd)
        sale_price_usd = money(sale_price_usd) if sale_price_usd else None
        slug = slugify(name)
        defaults = {
            'name': name,
            'brand': brand_name,
            'brand_fk': brands[brand_name],
            'category': category,
            'short_description': short_description,
            'description': description or short_description,
            'price_usd': price_usd,
            'sale_price_usd': sale_price_usd,
            'cost_price_usd': (price_usd * Decimal('0.48')).quantize(Decimal('0.01')),
            'price': usd_to_brl(price_usd, rate),
            'sale_price': usd_to_brl(sale_price_usd, rate) if sale_price_usd else None,
            'cost_price': usd_to_brl(price_usd * Decimal('0.48'), rate),
            'stock': stock,
            'status': status,
            'is_active': True,
            'is_featured': featured,
            'is_on_sale': on_sale,
            'is_pre_order': False,
            'is_fractioned': False,
            'has_variants': False,
            'weight': Decimal('0.350'),
            'height': Decimal('14'),
            'width': Decimal('8'),
            'length': Decimal('8'),
        }
        product, created = Product.objects.update_or_create(slug=slug, defaults=defaults)
        stats['products_created' if created else 'products_existing'] += 1
        return product

    def upsert_fractioned_product(self, category, brands, rate, stats, name, brand_name, variants, order=0):
        first_price = money(variants[0][1])
        total_stock = sum(stock for _, _, stock in variants)
        slug = slugify(name)
        defaults = {
            'name': name,
            'brand': brand_name,
            'brand_fk': brands[brand_name],
            'category': category,
            'short_description': 'Perfume fracionado original em decants de 10ml a 80ml.',
            'description': 'Produto demonstrativo para testar perfumes fracionados, volumes, estoque por variação e conversão dólar/real.',
            'price_usd': first_price,
            'sale_price_usd': None,
            'cost_price_usd': (first_price * Decimal('0.45')).quantize(Decimal('0.01')),
            'price': usd_to_brl(first_price, rate),
            'sale_price': None,
            'cost_price': usd_to_brl(first_price * Decimal('0.45'), rate),
            'stock': total_stock,
            'status': Product.STATUS_AVAILABLE if total_stock > 3 else Product.STATUS_LOW_STOCK,
            'is_active': True,
            'is_featured': order in (0, 3),
            'is_on_sale': False,
            'is_pre_order': False,
            'is_fractioned': True,
            'has_variants': True,
            'weight': Decimal('0.120'),
            'height': Decimal('12'),
            'width': Decimal('4'),
            'length': Decimal('4'),
        }
        product, created = Product.objects.update_or_create(slug=slug, defaults=defaults)
        stats['products_created' if created else 'products_existing'] += 1
        return product

    def upsert_variants(self, product, variants, rate, stats):
        for order, (volume, price, stock) in enumerate(variants):
            price_usd = money(price)
            promo_usd = (price_usd - Decimal('1.00')).quantize(Decimal('0.01')) if volume in (20, 50) and price_usd > 5 else None
            _, created = ProductVariant.objects.update_or_create(
                product=product,
                volume_ml=volume,
                defaults={
                    'name': f'{volume}ml',
                    'price_usd': price_usd,
                    'promotional_price_usd': promo_usd,
                    'cost_price_usd': (price_usd * Decimal('0.45')).quantize(Decimal('0.01')),
                    'stock': stock,
                    'is_active': True,
                    'order': order,
                    'sku': f'{product.slug.upper()[:18]}-{volume}ML',
                },
            )
            stats['variants_created' if created else 'variants_existing'] += 1
