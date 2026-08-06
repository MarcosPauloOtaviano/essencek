from django.db.models import Count, F, Q
from django.urls import reverse
from urllib.parse import urlencode

from .models import Product, Category


CATEGORY_GROUPS = {
    'perfumes': {
        'label': 'Perfumes',
        'nav_label': 'PERFUMES',
        'aria_label': 'Ver perfumes',
        'hint': 'Perfumes arabes, de nicho e para cabelo e corpo',
        'tokens': (
            'perfume', 'perfumes', 'nicho', 'arabe', 'árabe', 'arab',
            'cabelo-corpo', 'cabelo corpo',
        ),
    },
    'beleza-asiatica': {
        'label': 'Beleza Asiática',
        'nav_label': 'BELEZA ASIÁTICA',
        'aria_label': 'Ver beleza asiatica: skincare coreano e japones',
        'hint': 'Skincare coreano e japones',
        'tokens': (
            'k-beauty', 'k beauty', 'coreano', 'coreana', 'korean',
            'skincare-coreano', 'beleza-coreana', 'j-beauty', 'j beauty',
            'japonesa', 'japones', 'japan', 'beleza-japonesa',
        ),
    },
    'decanter': {
        'label': 'Decanter',
        'nav_label': 'DECANTER',
        'aria_label': 'Ver perfumes fracionados e decanters',
        'hint': 'Perfumes fracionados e decanters',
        'tokens': ('decanter', 'fracionado', 'decant', 'miniatura'),
    },
    'eletronicos': {
        'label': 'Eletrônicos',
        'nav_label': 'ELETRO',
        'aria_label': 'Ver eletrônicos',
        'hint': 'Eletronicos e tecnologia',
        'tokens': ('eletronico', 'eletronicos', 'eletrônico', 'eletrônicos', 'tecnologia'),
    },
}

CATEGORY_GROUP_ALIASES = {
    'k-beauty': 'beleza-asiatica',
    'kbeauty': 'beleza-asiatica',
}

LEGACY_CATEGORY_GROUPS = {
    'perfumes': 'perfumes',
    'beleza-coreana': 'beleza-asiatica',
    'decanter': 'decanter',
    'eletronicos': 'eletronicos',
}


def valid_sale_q():
    return (
        Q(is_on_sale=True)
        & Q(sale_price__isnull=False)
        & Q(sale_price__gt=0)
        & Q(sale_price__lt=F('price'))
        & ~Q(status=Product.STATUS_OUT_OF_STOCK)
    )


def catalog_url(**params):
    cleaned = {k: v for k, v in params.items() if v not in (None, '')}
    qs = urlencode(cleaned)
    return f'{reverse("products:list")}?{qs}' if qs else reverse('products:list')


def category_landing_url(category_key, **params):
    category_key = canonical_category_group(category_key)
    cleaned = {k: v for k, v in params.items() if v not in (None, '')}
    qs = urlencode(cleaned)
    url = reverse('category_landing', kwargs={'category_key': category_key})
    return f'{url}?{qs}' if qs else url


def active_category_queryset():
    return (
        Category.objects.filter(is_active=True)
        .select_related('parent')
        .annotate(
            active_product_count=Count(
                'products',
                filter=Q(products__is_active=True),
                distinct=True,
            )
        )
        .order_by('order', 'name')
    )


def attach_category_totals(categories):
    categories = list(categories)
    direct_counts = {
        cat.pk: getattr(cat, 'active_product_count', 0) or 0
        for cat in categories
    }
    total_counts = dict(direct_counts)
    parent_by_id = {cat.pk: cat.parent_id for cat in categories}

    for cat in categories:
        parent_id = cat.parent_id
        direct_count = direct_counts.get(cat.pk, 0)
        while parent_id:
            total_counts[parent_id] = total_counts.get(parent_id, 0) + direct_count
            parent_id = parent_by_id.get(parent_id)

    for cat in categories:
        cat.total_active_product_count = total_counts.get(cat.pk, 0)
    return categories


def public_categories_with_products():
    categories = attach_category_totals(active_category_queryset())
    return [
        cat for cat in categories
        if getattr(cat, 'total_active_product_count', 0) > 0
    ]


def _category_blob(category):
    return f'{category.slug or ""} {category.name or ""}'.casefold()


def canonical_category_group(group_slug):
    normalized = str(group_slug or '').casefold()
    return CATEGORY_GROUP_ALIASES.get(normalized, normalized)


def is_category_group(group_slug):
    return canonical_category_group(group_slug) in CATEGORY_GROUPS


def get_category_group_label(group_slug):
    canonical_group = canonical_category_group(group_slug)
    return CATEGORY_GROUPS.get(canonical_group, {}).get(
        'label',
        canonical_group.replace('-', ' ').title(),
    )


def category_group_from_legacy_slug(category_slug):
    return LEGACY_CATEGORY_GROUPS.get(str(category_slug or '').casefold())


def category_matches_group(category, group_slug):
    group = CATEGORY_GROUPS.get(canonical_category_group(group_slug))
    if not group:
        return False
    blob = _category_blob(category)
    return any(token.casefold() in blob for token in group['tokens'])


def category_ids_for_group(categories, group_slug):
    group_slug = canonical_category_group(group_slug)
    categories = list(categories)
    matching_ids = {
        cat.pk for cat in categories
        if category_matches_group(cat, group_slug)
    }

    changed = True
    while changed:
        changed = False
        for cat in categories:
            if cat.parent_id in matching_ids and cat.pk not in matching_ids:
                matching_ids.add(cat.pk)
                changed = True

    return sorted(matching_ids)


def count_group_products(categories, group_slug):
    ids = set(category_ids_for_group(categories, group_slug))
    return sum(
        getattr(cat, 'active_product_count', 0) or 0
        for cat in categories
        if cat.pk in ids
    )


def catalog_visibility():
    return Product.objects.filter(is_active=True).aggregate(
        offers=Count('pk', filter=valid_sale_q()),
        featured=Count('pk', filter=Q(is_featured=True)),
        available=Count('pk', filter=Q(status=Product.STATUS_AVAILABLE)),
    )


def build_quick_nav(categories=None, visibility=None):
    categories = attach_category_totals(active_category_queryset() if categories is None else categories)
    visibility = visibility or catalog_visibility()
    items = []

    if visibility['offers']:
        items.append({
            'label': 'OFERTAS',
            'url': reverse('offers'),
            'aria_label': 'Ver ofertas',
            'hint': 'Produtos com preco promocional valido',
        })

    for group_slug in ('perfumes', 'beleza-asiatica', 'decanter', 'eletronicos'):
        group = CATEGORY_GROUPS[group_slug]
        if count_group_products(categories, group_slug) > 0:
            items.append({
                'label': group['nav_label'],
                'url': category_landing_url(group_slug),
                'aria_label': group['aria_label'],
                'hint': group['hint'],
                'long_label': group_slug == 'beleza-asiatica',
            })

    if visibility['featured']:
        items.append({
            'label': 'DESTAQUES',
            'url': reverse('featured_products'),
            'aria_label': 'Ver produtos em destaque',
            'hint': 'Produtos selecionados em destaque',
        })

    if visibility['available']:
        items.append({
            'label': 'PRONTA ENTREGA',
            'url': reverse('available_products'),
            'aria_label': 'Ver produtos a pronta entrega',
            'hint': 'Produtos disponiveis para envio agora',
        })

    return items


def build_main_navigation(categories=None, visibility=None):
    categories = attach_category_totals(active_category_queryset() if categories is None else categories)
    visibility = visibility or catalog_visibility()
    items = [
        {'label': 'Home', 'url': reverse('home'), 'class': ''},
        {'label': 'Todos os produtos', 'url': reverse('products:list'), 'class': ''},
    ]

    for group_slug in ('perfumes', 'beleza-asiatica', 'decanter', 'eletronicos'):
        group = CATEGORY_GROUPS[group_slug]
        if count_group_products(categories, group_slug) > 0:
            items.append({
                'label': group['label'],
                'url': category_landing_url(group_slug),
                'class': '',
            })

    if visibility['offers']:
        items.append({'label': 'Promoções', 'url': reverse('offers'), 'class': 'nav-sale'})

    return items


def find_category_by_slug(categories, category_slug):
    if not category_slug:
        return None
    category_slug_folded = category_slug.casefold()
    return (
        next((c for c in categories if c.slug == category_slug), None)
        or next((c for c in categories if c.slug.casefold() == category_slug_folded), None)
    )


def build_filter_tree(all_categories, category_slug, brand_slug, perfume_type, query):
    categories_by_parent = {}
    for cat in all_categories:
        categories_by_parent.setdefault(cat.parent_id, []).append(cat)

    active_category = None
    active_root = None
    active_root_slug = ''
    if category_slug:
        active_category = find_category_by_slug(all_categories, category_slug)
        if active_category:
            active_root = active_category.parent if active_category.parent else active_category
            active_root_slug = active_root.slug

    parent_by_id = {cat.pk: cat.parent_id for cat in all_categories}

    def root_id_for(category_id):
        current_id = category_id
        visited = set()
        while parent_by_id.get(current_id) and current_id not in visited:
            visited.add(current_id)
            current_id = parent_by_id[current_id]
        return current_id

    stats_by_root = {}
    category_ids = list(parent_by_id)
    grouped_rows = (
        Product.objects.filter(is_active=True, category_id__in=category_ids)
        .values(
            'category_id',
            'brand_fk_id',
            'brand_fk__name',
            'brand_fk__slug',
            'brand_fk__is_active',
            'is_fractioned',
        )
        .annotate(count=Count('pk'))
        .order_by()
    )
    for row in grouped_rows:
        root_id = root_id_for(row['category_id'])
        stats = stats_by_root.setdefault(root_id, {
            'traditional_count': 0,
            'fractioned_count': 0,
            'brands': {},
        })
        count = row['count']
        type_key = 'fractioned_count' if row['is_fractioned'] else 'traditional_count'
        stats[type_key] += count
        if row['brand_fk_id'] and row['brand_fk__is_active']:
            brand = stats['brands'].setdefault(row['brand_fk_id'], {
                'brand_fk__pk': row['brand_fk_id'],
                'brand_fk__name': row['brand_fk__name'],
                'brand_fk__slug': row['brand_fk__slug'],
                'count': 0,
            })
            brand['count'] += count

    tree = []
    parent_categories = categories_by_parent.get(None, [])
    for parent in parent_categories:
        subcategories = categories_by_parent.get(parent.pk, [])
        stats = stats_by_root.get(parent.pk, {
            'traditional_count': 0,
            'fractioned_count': 0,
            'brands': {},
        })
        brand_counts = sorted(
            stats['brands'].values(),
            key=lambda brand: (brand['brand_fk__name'] or '').casefold(),
        )

        is_open = active_root_slug == parent.slug
        scope_slug = active_category.slug if is_open and active_category else parent.slug

        is_perfume_category = (
            parent.slug in ('perfumes', 'decanter')
            or category_matches_group(parent, 'perfumes')
            or category_matches_group(parent, 'decanter')
        )

        node = {
            'name': parent.name,
            'slug': parent.slug,
            'is_active': active_category and active_category.pk == parent.pk,
            'is_open': is_open,
            'url': category_landing_url(parent.slug, q=query),
            'subcategories': [
                {
                    'name': sub.name,
                    'slug': sub.slug,
                    'is_active': active_category and active_category.pk == sub.pk,
                    'url': category_landing_url(sub.slug, q=query),
                }
                for sub in subcategories
            ],
            'brands': [
                {
                    'name': bc['brand_fk__name'],
                    'slug': bc['brand_fk__slug'],
                    'count': bc['count'],
                    'is_active': brand_slug == bc['brand_fk__slug'] and is_open,
                    'url': catalog_url(
                        category=scope_slug,
                        brand=bc['brand_fk__slug'],
                        perfume_type=perfume_type if is_open and perfume_type else '',
                        q=query,
                    ),
                }
                for bc in brand_counts
            ],
            'is_perfume': is_perfume_category,
            'perfume_types': [],
        }

        if is_perfume_category:
            traditional_count = stats['traditional_count']
            fractioned_count = stats['fractioned_count']
            types = []
            if traditional_count > 0:
                types.append({
                    'label': 'Tradicional / lacrado',
                    'value': 'tradicional',
                    'count': traditional_count,
                    'is_active': perfume_type == 'tradicional' and is_open,
                    'url': catalog_url(
                        category=scope_slug,
                        brand=brand_slug if is_open else '',
                        perfume_type='tradicional',
                        q=query,
                    ),
                })
            if fractioned_count > 0:
                types.append({
                    'label': 'Fracionado / decanter',
                    'value': 'fracionado',
                    'count': fractioned_count,
                    'is_active': perfume_type == 'fracionado' and is_open,
                    'url': catalog_url(
                        category=scope_slug,
                        brand=brand_slug if is_open else '',
                        perfume_type='fracionado',
                        q=query,
                    ),
                })
            node['perfume_types'] = types

        node['has_children'] = bool(node['subcategories'] or node['brands'] or node['perfume_types'])
        tree.append(node)

    return tree, active_category, active_root_slug


def build_breadcrumbs(active_category, active_brand_name, perfume_type_label, category_slug, brand_slug):
    items = [{'label': 'Produtos', 'url': reverse('products:list')}]
    if active_category:
        has_deeper = bool(active_brand_name or perfume_type_label)
        if active_category.parent:
            items.append({
                'label': active_category.parent.name,
                'url': catalog_url(category=active_category.parent.slug),
            })
        items.append({
            'label': active_category.name,
            'url': catalog_url(category=active_category.slug) if has_deeper else '',
        })
    elif active_brand_name:
        items.append({'label': 'Marca', 'url': ''})

    if active_brand_name:
        items.append({
            'label': active_brand_name,
            'url': catalog_url(category=category_slug, brand=brand_slug) if perfume_type_label else '',
        })
    if perfume_type_label:
        items.append({'label': perfume_type_label, 'url': ''})

    return items
