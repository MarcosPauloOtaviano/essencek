from django.urls import reverse
from urllib.parse import urlencode

from .models import Brand, Product, Category


LOGICAL_CATEGORY_BRAND_SLUGS = {
    'perfumes': [
        'carolina-herrera', 'chanel', 'dior', 'jean-paul-gaultier',
        'lancome', 'lattafa', 'paco-rabanne', 'yves-saint-laurent',
    ],
    'decanter': [
        'carolina-herrera', 'chanel', 'dior', 'jean-paul-gaultier',
        'lancome', 'lattafa', 'paco-rabanne', 'yves-saint-laurent',
    ],
    'beleza-coreana': ['beauty-of-joseon', 'cosrx', 'laneige'],
    'eletronicos': ['anker', 'apple', 'samsung'],
}

LOGICAL_CATEGORY_VOLUMES = {
    'perfumes': [30, 50, 60, 75, 80, 100, 125, 150, 200],
    'decanter': [2, 3, 5, 7, 10],
}


def catalog_url(**params):
    cleaned = {k: v for k, v in params.items() if v not in (None, '')}
    qs = urlencode(cleaned)
    return f'{reverse("products:list")}?{qs}' if qs else reverse('products:list')


def build_filter_tree(all_categories, category_slug, brand_slug, selected_volume_ml, query):
    categories_by_parent = {}
    for cat in all_categories:
        categories_by_parent.setdefault(cat.parent_id, []).append(cat)

    active_category = None
    active_root = None
    active_root_slug = ''
    if category_slug:
        active_category = next((c for c in all_categories if c.slug == category_slug), None)
        if active_category:
            active_root = active_category.parent if active_category.parent else active_category
            active_root_slug = active_root.slug

    tree = []
    parent_categories = categories_by_parent.get(None, [])
    for parent in parent_categories:
        subcategories = categories_by_parent.get(parent.pk, [])
        category_ids = [parent.pk, *[sub.pk for sub in subcategories]]
        scoped_products = Product.objects.filter(is_active=True, category_id__in=category_ids)

        logical_brand_slugs = LOGICAL_CATEGORY_BRAND_SLUGS.get(parent.slug)
        if logical_brand_slugs:
            brand_order = {slug: i for i, slug in enumerate(logical_brand_slugs)}
            category_brands = sorted(
                Brand.objects.filter(slug__in=logical_brand_slugs, is_active=True),
                key=lambda b: brand_order.get(b.slug, 999),
            )
        else:
            brand_ids = (
                scoped_products.filter(brand_fk__isnull=False)
                .values_list('brand_fk', flat=True).distinct()
            )
            category_brands = Brand.objects.filter(pk__in=brand_ids, is_active=True).order_by('name')

        logical_volumes = LOGICAL_CATEGORY_VOLUMES.get(parent.slug)
        if logical_volumes:
            volume_values = logical_volumes
        else:
            volume_values = (
                scoped_products.filter(variants__is_active=True, variants__volume_ml__isnull=False)
                .values_list('variants__volume_ml', flat=True)
                .distinct().order_by('variants__volume_ml')
            )

        is_open = active_root_slug == parent.slug
        scope_slug = active_category.slug if is_open and active_category else parent.slug
        node = {
            'name': parent.name,
            'slug': parent.slug,
            'is_active': category_slug == parent.slug,
            'is_open': is_open,
            'url': catalog_url(category=parent.slug, q=query),
            'subcategories': [
                {
                    'name': sub.name,
                    'slug': sub.slug,
                    'is_active': category_slug == sub.slug,
                    'url': catalog_url(category=sub.slug, q=query),
                }
                for sub in subcategories
            ],
            'brands': [
                {
                    'name': b.name,
                    'slug': b.slug,
                    'is_active': brand_slug == b.slug and is_open,
                    'url': catalog_url(
                        category=scope_slug,
                        brand=b.slug,
                        volume=selected_volume_ml if is_open and selected_volume_ml else '',
                        q=query,
                    ),
                }
                for b in category_brands
            ],
            'volumes': [
                {
                    'label': f'{vol}ml',
                    'value': vol,
                    'is_active': selected_volume_ml == vol and is_open,
                    'url': catalog_url(
                        category=scope_slug,
                        brand=brand_slug if is_open else '',
                        volume=vol,
                        q=query,
                    ),
                }
                for vol in volume_values if vol
            ],
        }
        node['has_children'] = bool(node['subcategories'] or node['brands'] or node['volumes'])
        tree.append(node)

    return tree, active_category, active_root_slug


def build_breadcrumbs(active_category, active_brand_name, selected_volume_label, category_slug, brand_slug):
    items = [{'label': 'Produtos', 'url': reverse('products:list')}]
    if active_category:
        has_deeper = bool(active_brand_name or selected_volume_label)
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
            'url': catalog_url(category=category_slug, brand=brand_slug) if selected_volume_label else '',
        })
    if selected_volume_label:
        items.append({'label': selected_volume_label, 'url': ''})

    return items
