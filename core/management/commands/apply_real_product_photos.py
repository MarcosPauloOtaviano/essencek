from pathlib import Path
from urllib.parse import urlparse

import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from products.models import Product, ProductImage


REAL_ALT_PREFIX = 'Foto real demonstrativa'
REQUEST_TIMEOUT = 30
USER_AGENT = 'EssenceKImageSync/1.0 (local development)'


def pexels_url(photo_id):
    return (
        f'https://images.pexels.com/photos/{photo_id}/pexels-photo-{photo_id}.jpeg'
        '?auto=compress&cs=tinysrgb&w=1200&h=1200&fit=crop'
    )


OPEN_BEAUTY_SOURCES = {
    'good-girl-eau-de-parfum': 'https://images.openbeautyfacts.org/images/products/841/106/181/9838/front_fr.8.400.jpg',
    'good-girl-fracionado': 'https://images.openbeautyfacts.org/images/products/841/106/181/9838/front_fr.8.400.jpg',
    'coco-mademoiselle': 'https://images.openbeautyfacts.org/images/products/314/589/116/5203/front_fr.6.400.jpg',
    'la-vie-est-belle': 'https://images.openbeautyfacts.org/images/products/360/553/261/2768/front_en.6.400.jpg',
    'la-vie-est-belle-fracionado': 'https://images.openbeautyfacts.org/images/products/360/553/261/2768/front_en.6.400.jpg',
    'libre-eau-de-parfum': 'https://images.openbeautyfacts.org/images/products/361/427/264/8418/front_nl.12.400.jpg',
    'libre-fracionado': 'https://images.openbeautyfacts.org/images/products/361/427/264/8418/front_nl.12.400.jpg',
    'sauvage-eau-de-parfum': 'https://images.openbeautyfacts.org/images/products/334/890/129/2276/front_en.3.400.jpg',
    'sauvage-fracionado': 'https://images.openbeautyfacts.org/images/products/334/890/129/2276/front_en.3.400.jpg',
    'scandal': 'https://images.openbeautyfacts.org/images/products/843/541/502/2033/front_fr.4.400.jpg',
    'scandal-fracionado': 'https://images.openbeautyfacts.org/images/products/843/541/502/2033/front_fr.4.400.jpg',
    'glow-serum-propolis-niacinamide': 'https://images.openbeautyfacts.org/images/products/880/965/711/4960/front_en.6.400.jpg',
    'low-ph-good-morning-gel-cleanser': 'https://images.openbeautyfacts.org/images/products/880/941/647/0511/front_en.15.400.jpg',
    'lip-sleeping-mask-berry': 'https://images.openbeautyfacts.org/images/products/880/964/305/3273/front_en.4.400.jpg',
    'relief-sun-rice-probiotics-spf50': 'https://images.openbeautyfacts.org/images/products/880/996/813/0277/front_nl.21.400.jpg',
}


PEXELS_SOURCES = {
    '212-vip-rose': 15096784,
    '212-vip-rose-fracionado': 29022731,
    'lady-million': 4735908,
    'lady-million-fracionado': 29022731,
    'body-splash-luxo': 29022731,
    'perfume-feminino-elegance': 4735908,
    'perfume-importado-premium': 15096784,
    'advanced-snail-96-mucin-essence': 3762879,
    'creme-clareador-coreano': 36339062,
    'mascara-facial-hidratante': 3851674,
    'serum-facial-coreano': 3762879,
    'caixa-de-som-portatil': 4917455,
    'caixa-de-som-portatil-mini': 1034653,
    'carregador-turbo-usb-c': 32710069,
    'fone-bluetooth-premium': 3394650,
    'iphone-seminovo-selecionado': 14665637,
    'smartwatch-elegance-rose': 10357003,
    'smartwatch-ultra': 3646165,
}


FALLBACK_POOLS = {
    'perfume': [15096784, 264819, 4735908],
    'fractioned': [29022731, 15096784, 264819],
    'kbeauty': [3762879, 3851674, 8131568, 36339062],
    'tech': [3394650, 31406895, 4917455, 5269699],
    'default': [7703038],
}


def product_kind(product):
    category_slug = product.category.slug if product.category else ''
    text = ' '.join([
        product.name or '',
        product.short_description or '',
        product.description or '',
        category_slug,
    ]).casefold()

    if product.is_fractioned or 'fracionado' in text:
        return 'fractioned'
    if any(token in text for token in ['perfume', 'parfum', 'splash', 'eau de']):
        return 'perfume'
    if any(token in text for token in ['serum', 'sérum', 'snail', 'cream', 'creme', 'mask', 'máscara', 'cleanser', 'sun', 'probiotics', 'lip']):
        return 'kbeauty'
    if any(token in text for token in ['fone', 'smartwatch', 'iphone', 'carregador', 'caixa de som', 'bluetooth', 'usb']):
        return 'tech'
    if category_slug == 'beleza-coreana':
        return 'kbeauty'
    if category_slug == 'eletronicos':
        return 'tech'
    if category_slug in {'perfumes', 'perfumes-fracionados'}:
        return 'perfume'
    return 'default'


def fallback_photo_for(product):
    kind = product_kind(product)
    pool = FALLBACK_POOLS.get(kind, FALLBACK_POOLS['default'])
    index = sum(ord(char) for char in product.slug) % len(pool)
    photo_id = pool[index]
    return pexels_url(photo_id), f'Pexels #{photo_id}'


def source_for(product):
    if product.slug in OPEN_BEAUTY_SOURCES:
        return OPEN_BEAUTY_SOURCES[product.slug], 'Open Beauty Facts'
    if product.slug in PEXELS_SOURCES:
        photo_id = PEXELS_SOURCES[product.slug]
        return pexels_url(photo_id), f'Pexels #{photo_id}'
    return fallback_photo_for(product)


def extension_from_response(url, response):
    content_type = response.headers.get('content-type', '').lower()
    if 'png' in content_type:
        return 'png'
    if 'webp' in content_type:
        return 'webp'
    ext = Path(urlparse(url).path).suffix.lower().lstrip('.')
    if ext in {'jpg', 'jpeg', 'png', 'webp'}:
        return ext
    return 'jpg'


class Command(BaseCommand):
    help = 'Baixa fotos reais para arquivos locais e aplica como imagem principal dos produtos.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--only-missing-real',
            action='store_true',
            help='Não atualiza produtos que já possuem uma foto real demonstrativa.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra o que seria atualizado sem salvar alterações.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        only_missing_real = options['only_missing_real']
        created = 0
        updated = 0
        skipped = 0
        errors = []

        products = Product.objects.select_related('category', 'brand_fk').prefetch_related('images').order_by('name')
        for product in products:
            existing_real = product.images.filter(alt_text__startswith=REAL_ALT_PREFIX).first()
            if only_missing_real and existing_real:
                skipped += 1
                self.stdout.write(f'PULADO {product.name} - ja possui foto real')
                continue

            url, source = source_for(product)
            self.stdout.write(f'BAIXANDO {product.name} <- {source}')
            if dry_run:
                skipped += 1
                continue

            try:
                response = requests.get(url, timeout=REQUEST_TIMEOUT, headers={'User-Agent': USER_AGENT})
                response.raise_for_status()
                if not response.headers.get('content-type', '').startswith('image/'):
                    raise CommandError(f'URL nao retornou imagem: {url}')
            except requests.RequestException as exc:
                errors.append(f'{product.name}: {exc}')
                self.stderr.write(self.style.WARNING(f'ERRO {product.name}: {exc}'))
                continue

            ProductImage.objects.filter(product=product, is_main=True).update(is_main=False)
            image = existing_real or ProductImage(product=product)
            image.alt_text = f'{REAL_ALT_PREFIX}: {product.name} ({source})'[:200]
            image.is_main = True
            image.order = 0
            ext = extension_from_response(url, response)
            filename = f'foto-real-{slugify(product.slug or product.name)}.{ext}'
            image.image.save(filename, ContentFile(response.content, name=filename), save=True)

            if existing_real:
                updated += 1
            else:
                created += 1

        message = f'Fotos reais aplicadas. Criadas: {created}. Atualizadas: {updated}. Puladas: {skipped}. Erros: {len(errors)}.'
        if errors:
            self.stdout.write(self.style.WARNING(message))
            for error in errors:
                self.stdout.write(self.style.WARNING(f'- {error}'))
        else:
            self.stdout.write(self.style.SUCCESS(message))
