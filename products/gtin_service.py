import logging
import requests
from django.conf import settings
from django.db.models import Q
from django.urls import reverse
from .gtin_catalog import LOCAL_GTIN_PRODUCTS

logger = logging.getLogger('products.gtin')

TIMEOUT = 8
VALID_GTIN_LENGTHS = {8, 12, 13, 14}


def normalize_gtin(code):
    return ''.join(char for char in str(code or '') if char.isdigit())


def gtin_candidates(code):
    normalized = normalize_gtin(code)
    if not normalized:
        return []

    candidates = [normalized]
    if len(normalized) == 12:
        candidates.append(f'0{normalized}')
    if len(normalized) == 13 and normalized.startswith('0'):
        candidates.append(normalized[1:])
    if len(normalized) == 14 and normalized.startswith('0'):
        candidates.append(normalized[1:])

    seen = set()
    return [value for value in candidates if not (value in seen or seen.add(value))]


def is_supported_gtin(code):
    return len(normalize_gtin(code)) in VALID_GTIN_LENGTHS


def lookup_product_identifier(value, include_local=True, limit=8):
    raw = str(value or '').strip()
    numeric = normalize_gtin(raw)
    logger.info('GTIN lookup: raw=%r numeric=%r len_numeric=%d', raw, numeric, len(numeric))

    if numeric and len(numeric) == len(raw.replace(' ', '').replace('-', '')):
        if is_supported_gtin(numeric):
            result = lookup_gtin(numeric, include_local=include_local)
            if result:
                logger.info('GTIN found via lookup_gtin: source=%s name=%s', result.get('source'), result.get('name'))
                return result
            logger.info('GTIN not found in any source, returning draft for code=%s', numeric)
            return _draft_unknown_code(numeric)
        logger.info('GTIN length %d not supported, returning draft', len(numeric))
        return _draft_unknown_code(numeric)

    result = _try_existing_product_text(raw, limit=limit)
    if result:
        logger.info('Text search found existing product: name=%s', result.get('name'))
        return result

    result = _try_local_catalog_text(raw)
    if result:
        logger.info('Text search found in local catalog: name=%s', result.get('name'))
        return result

    cosmos_token = getattr(settings, 'COSMOS_API_TOKEN', '')
    if cosmos_token:
        result = _try_cosmos_text_search(raw, cosmos_token)
        if result:
            logger.info('Text search found in Cosmos: name=%s', result.get('name'))
            return result

    logger.info('No results for query=%r', raw)
    return None


def lookup_gtin(code, include_local=True):
    candidates = gtin_candidates(code)
    if not candidates:
        return None

    if include_local:
        result = _try_existing_product(candidates)
        if result:
            return result

    result = _try_local_catalog(candidates)
    if result:
        return result

    result = _try_open_facts_api(candidates[0], 'https://world.openfoodfacts.org', 'open_food_facts')
    if result:
        return result

    result = _try_open_facts_api(candidates[0], 'https://world.openbeautyfacts.org', 'open_beauty_facts')
    if result:
        return result

    cosmos_token = getattr(settings, 'COSMOS_API_TOKEN', '')
    if cosmos_token:
        result = _try_cosmos(candidates[0], cosmos_token)
        if result:
            return result

    return None


def _draft_unknown_code(code):
    return {
        'name': f'Produto sem cadastro - {code}',
        'brand': '',
        'description': 'Código lido, mas ainda sem dados em catálogo. Complete nome, marca, categoria, preço e foto para salvar.',
        'image_url': '',
        'gtin': code,
        'source': 'codigo_lido_sem_catalogo',
        'existing': False,
        'draft': True,
        'message': 'Código lido com sucesso, mas sem dados automáticos. Você pode cadastrar manualmente mantendo este código.',
    }


def _product_payload(product, source='produto_cadastrado'):
    return {
        'name': product.name,
        'brand': product.display_brand,
        'description': product.description or product.short_description,
        'image_url': _safe_product_image_url(product),
        'gtin': product.gtin or '',
        'source': source,
        'existing': True,
        'product_id': product.pk,
        'product_url': product.get_absolute_url(),
        'edit_url': reverse('dashboard:product_edit', args=[product.pk]),
    }


def _try_existing_product(candidates):
    from .models import Product, ProductVariant

    product = (
        Product.objects.filter(gtin__in=candidates)
        .select_related('category', 'brand_fk')
        .first()
    )
    if product:
        return _product_payload(product)

    variant = (
        ProductVariant.objects.filter(gtin__in=candidates)
        .select_related('product', 'product__category', 'product__brand_fk')
        .first()
    )
    if variant:
        product = variant.product
        return {
            'name': product.name,
            'brand': product.display_brand,
            'description': product.description or product.short_description,
            'image_url': _safe_product_image_url(product),
            'gtin': variant.gtin,
            'source': 'variacao_cadastrada',
            'existing': True,
            'product_id': product.pk,
            'variant_id': variant.pk,
            'variant_name': variant.name,
            'product_url': product.get_absolute_url(),
            'edit_url': reverse('dashboard:product_edit', args=[product.pk]),
        }
    return None


def _try_existing_product_text(query, limit=8):
    from .models import Product, ProductVariant

    query = (query or '').strip()
    if len(query) < 2:
        return None

    products = list(
        Product.objects.filter(
            Q(name__icontains=query) |
            Q(brand__icontains=query) |
            Q(brand_fk__name__icontains=query) |
            Q(short_description__icontains=query) |
            Q(description__icontains=query)
        )
        .select_related('category', 'brand_fk')
        .distinct()
        .order_by('name')[:limit]
    )

    variant_matches = list(
        ProductVariant.objects.filter(
            Q(name__icontains=query) |
            Q(sku__icontains=query) |
            Q(product__name__icontains=query) |
            Q(product__brand__icontains=query) |
            Q(product__brand_fk__name__icontains=query)
        )
        .select_related('product', 'product__category', 'product__brand_fk')
        .distinct()
        .order_by('product__name', 'order')[:limit]
    )
    for variant in variant_matches:
        if variant.product not in products:
            products.append(variant.product)
        if len(products) >= limit:
            break

    if not products:
        return None
    if len(products) == 1:
        return _product_payload(products[0], source='busca_local')

    return {
        'name': products[0].name,
        'brand': products[0].display_brand,
        'description': products[0].description or products[0].short_description,
        'image_url': _safe_product_image_url(products[0]),
        'gtin': products[0].gtin or '',
        'source': 'busca_local',
        'existing': True,
        'product_id': products[0].pk,
        'product_url': products[0].get_absolute_url(),
        'edit_url': reverse('dashboard:product_edit', args=[products[0].pk]),
        'matches': [_product_payload(product, source='busca_local') for product in products],
    }


def _safe_product_image_url(product):
    try:
        return product.display_image_url
    except (OSError, ValueError):
        return ''


def _try_local_catalog(candidates):
    for candidate in candidates:
        product = LOCAL_GTIN_PRODUCTS.get(candidate)
        if product:
            return _normalize(
                product.get('name', ''),
                product.get('brand', ''),
                product.get('description', ''),
                product.get('image_url', ''),
                gtin=candidate,
                source=product.get('source', 'catalogo_local'),
                category_slug=product.get('category_slug', ''),
            )
    return None


def _try_local_catalog_text(query):
    query = (query or '').casefold().strip()
    if len(query) < 2:
        return None

    for code, product in LOCAL_GTIN_PRODUCTS.items():
        haystack = ' '.join([
            product.get('name', ''),
            product.get('brand', ''),
            product.get('description', ''),
            code,
        ]).casefold()
        if query in haystack:
            return _normalize(
                product.get('name', ''),
                product.get('brand', ''),
                product.get('description', ''),
                product.get('image_url', ''),
                gtin=code,
                source=product.get('source', 'catalogo_local'),
                category_slug=product.get('category_slug', ''),
            )
    return None


def _try_open_facts_api(code, base_url, source):
    try:
        url = f'{base_url}/api/v2/product/{code}.json'
        label = source.replace('_', ' ').title()
        logger.info('Querying %s for %s', label, code)
        resp = requests.get(url, timeout=TIMEOUT, headers={'User-Agent': 'EssenceK/1.0'})
        if resp.status_code != 200:
            logger.info('%s returned HTTP %d for %s', label, resp.status_code, code)
            return None
        data = resp.json()
        if data.get('status') != 1:
            logger.info('%s: product not found for %s', label, code)
            return None
        product = data.get('product', {})
        name = product.get('product_name', '')
        logger.info('%s: found "%s" for %s', label, name, code)
        return _normalize(
            name,
            product.get('brands', ''),
            product.get('generic_name', '') or product.get('categories', ''),
            product.get('image_front_url', ''),
            gtin=code,
            source=source,
        )
    except requests.Timeout:
        logger.warning('%s timeout for %s', label, code)
        return None
    except Exception:
        logger.warning('%s lookup failed for %s', label, code, exc_info=True)
        return None


def _cosmos_headers(token):
    return {
        'X-Cosmos-Token': token,
        'Content-Type': 'application/json',
        'User-Agent': 'Cosmos-API-Request',
    }


def _parse_cosmos_product(data, gtin=''):
    name = data.get('description', '')
    brand_data = data.get('brand')
    brand = brand_data.get('name', '') if isinstance(brand_data, dict) else ''
    ncm_data = data.get('ncm')
    description = ncm_data.get('full_description', '') if isinstance(ncm_data, dict) else ''
    thumbnail = data.get('thumbnail', '')
    return _normalize(name, brand, description, thumbnail, gtin=gtin or str(data.get('gtin', '')), source='cosmos')


def _try_cosmos(code, token):
    try:
        url = f'https://api.cosmos.bluesoft.com.br/gtins/{code}'
        logger.info('Querying Cosmos for %s', code)
        resp = requests.get(url, timeout=TIMEOUT, headers=_cosmos_headers(token))
        if resp.status_code != 200:
            logger.info('Cosmos returned HTTP %d for %s', resp.status_code, code)
            return None
        data = resp.json()
        name = data.get('description', '')
        logger.info('Cosmos: found "%s" for %s', name, code)
        return _parse_cosmos_product(data, gtin=code)
    except requests.Timeout:
        logger.warning('Cosmos timeout for %s', code)
        return None
    except Exception:
        logger.warning('Cosmos lookup failed for %s', code, exc_info=True)
        return None


def _try_cosmos_text_search(query, token):
    try:
        url = 'https://api.cosmos.bluesoft.com.br/products'
        logger.info('Querying Cosmos text search for %r', query)
        resp = requests.get(url, params={'query': query}, timeout=TIMEOUT, headers=_cosmos_headers(token))
        if resp.status_code != 200:
            logger.info('Cosmos text search returned HTTP %d', resp.status_code)
            return None
        data = resp.json()
        products = data.get('products', [])
        if not products:
            return None
        logger.info('Cosmos text search: found %d result(s) for %r', len(products), query)
        return _parse_cosmos_product(products[0])
    except requests.Timeout:
        logger.warning('Cosmos text search timeout for %r', query)
        return None
    except Exception:
        logger.warning('Cosmos text search failed for %r', query, exc_info=True)
        return None


def _normalize(name, brand, description, image_url, gtin='', source='', category_slug=''):
    name = (name or '').strip()
    if not name:
        return None
    result = {
        'name': name,
        'brand': (brand or '').strip(),
        'description': (description or '').strip(),
        'image_url': (image_url or '').strip(),
        'gtin': normalize_gtin(gtin),
        'source': source,
        'existing': False,
    }
    if category_slug:
        from .models import Category
        category = Category.objects.filter(slug=category_slug, is_active=True).first()
        if category:
            result['category_id'] = category.pk
            result['category_name'] = category.name
            result['category_slug'] = category.slug
    return result
