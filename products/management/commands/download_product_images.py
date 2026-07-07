import logging
import time

import requests
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from products.image_downloader import download_and_process_image
from products.models import Product, ProductImage

logger = logging.getLogger('products.gtin')

TIMEOUT = 10


def _build_search_terms(product):
    parts = [product.name]
    if product.brand_fk:
        parts.append(product.brand_fk.name)
    elif product.brand:
        parts.append(product.brand)
    if product.category:
        parts.append(product.category.name)
    return ' '.join(parts)


def _search_open_facts(query, base_url):
    try:
        resp = requests.get(
            f'{base_url}/cgi/search.pl',
            params={'search_terms': query, 'search_simple': 1, 'json': 1, 'page_size': 5},
            timeout=TIMEOUT,
            headers={'User-Agent': 'EssenceK/1.0'},
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        urls = []
        for p in data.get('products', []):
            url = p.get('image_front_url', '')
            if url and url.startswith('http'):
                urls.append(url)
        return urls
    except Exception:
        return []


def _search_by_gtin(gtin):
    urls = []
    for base_url in ['https://world.openfoodfacts.org', 'https://world.openbeautyfacts.org']:
        try:
            resp = requests.get(
                f'{base_url}/api/v2/product/{gtin}.json',
                timeout=TIMEOUT,
                headers={'User-Agent': 'EssenceK/1.0'},
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            if data.get('status') != 1:
                continue
            product = data.get('product', {})
            for key in ('image_front_url', 'image_url'):
                url = product.get(key, '')
                if url and url.startswith('http'):
                    urls.append(url)
        except Exception:
            continue

    from django.conf import settings
    token = getattr(settings, 'COSMOS_API_TOKEN', '')
    if token:
        try:
            resp = requests.get(
                f'https://api.cosmos.bluesoft.com.br/gtins/{gtin}',
                timeout=TIMEOUT,
                headers={'X-Cosmos-Token': token, 'User-Agent': 'EssenceK/1.0'},
            )
            if resp.status_code == 200:
                data = resp.json()
                thumb = data.get('thumbnail', '')
                if thumb and thumb.startswith('http'):
                    urls.append(thumb)
        except Exception:
            pass

    return urls


def find_image_urls(product):
    urls = []

    if product.gtin:
        urls.extend(_search_by_gtin(product.gtin))

    for variant in product.variants.filter(gtin__isnull=False).exclude(gtin=''):
        urls.extend(_search_by_gtin(variant.gtin))

    if not urls:
        query = _build_search_terms(product)
        urls.extend(_search_open_facts(query, 'https://world.openfoodfacts.org'))
        urls.extend(_search_open_facts(query, 'https://world.openbeautyfacts.org'))

    if not urls and product.name:
        short_query = product.name.split(' - ')[0].strip()
        urls.extend(_search_open_facts(short_query, 'https://world.openfoodfacts.org'))

    seen = set()
    unique = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


class Command(BaseCommand):
    help = 'Busca e baixa fotos reais de produtos usando GTIN e texto nos catálogos abertos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--product', '-p', type=int, default=None,
            help='ID de um produto específico (padrão: todos)',
        )
        parser.add_argument(
            '--replace', action='store_true',
            help='Substituir fotos existentes (padrão: só preenche produtos sem foto)',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Apenas mostra URLs encontradas sem baixar',
        )

    def handle(self, *args, **options):
        product_id = options['product']
        replace = options['replace']
        dry_run = options['dry_run']

        qs = Product.objects.select_related('category', 'brand_fk').prefetch_related('variants', 'images')
        if product_id:
            qs = qs.filter(pk=product_id)

        products = list(qs)
        self.stdout.write(f'\nAnalisando {len(products)} produto(s)...\n')

        stats = {'found': 0, 'downloaded': 0, 'skipped': 0, 'failed': 0}

        for product in products:
            has_images = product.images.exists()
            if has_images and not replace:
                self.stdout.write(f'  [{product.pk}] {product.name} — já tem foto, pulando')
                stats['skipped'] += 1
                continue

            self.stdout.write(f'  [{product.pk}] {product.name}')
            terms = _build_search_terms(product)
            self.stdout.write(f'       Termos: {terms}')

            urls = find_image_urls(product)
            if not urls:
                self.stdout.write(self.style.WARNING('       Nenhuma foto encontrada'))
                stats['failed'] += 1
                continue

            stats['found'] += 1
            self.stdout.write(f'       Encontradas {len(urls)} URL(s):')
            for url in urls[:3]:
                self.stdout.write(f'         - {url}')

            if dry_run:
                continue

            downloaded = False
            for url in urls[:3]:
                stem = slugify(product.name)[:60] or 'produto'
                image_file = download_and_process_image(url, filename_stem=stem)
                if image_file:
                    if replace and has_images:
                        for old_img in product.images.all():
                            try:
                                old_img.image.delete(save=False)
                            except Exception:
                                pass
                            old_img.delete()

                    ProductImage.objects.create(
                        product=product,
                        image=image_file,
                        alt_text=product.name,
                        is_main=True,
                        order=0,
                    )
                    product.images.filter(is_main=True).exclude(
                        pk=product.images.filter(is_main=True).order_by('-pk').first().pk
                    ).update(is_main=False)

                    self.stdout.write(self.style.SUCCESS(f'       OK: foto baixada e processada'))
                    stats['downloaded'] += 1
                    downloaded = True
                    break

                self.stdout.write(self.style.WARNING(f'       Falha ao processar: {url}'))

            if not downloaded:
                stats['failed'] += 1

            time.sleep(0.5)

        self.stdout.write(f'\n--- Resultado ---')
        self.stdout.write(f'  Encontradas: {stats["found"]}')
        self.stdout.write(f'  Baixadas:    {stats["downloaded"]}')
        self.stdout.write(f'  Puladas:     {stats["skipped"]}')
        self.stdout.write(f'  Sem foto:    {stats["failed"]}')
        self.stdout.write(self.style.SUCCESS('\nConcluído!'))
