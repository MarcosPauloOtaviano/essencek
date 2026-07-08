from django.db.models import Count, Q
from django.urls import reverse
from urllib.parse import urlencode

from .models import Brand, Product, Category


def catalog_url(**params):
    cleaned = {k: v for k, v in params.items() if v not in (None, '')}
    qs = urlencode(cleaned)
    return f'{reverse("products:list")}?{qs}' if qs else reverse('products:list')


def build_filter_tree(all_categories, category_slug, brand_slug, perfume_type, query):
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

        brand_counts = (
            scoped_products
            .filter(brand_fk__isnull=False, brand_fk__is_active=True)
            .values('brand_fk__pk', 'brand_fk__name', 'brand_fk__slug')
            .annotate(count=Count('pk'))
            .order_by('brand_fk__name')
        )

        is_open = active_root_slug == parent.slug
        scope_slug = active_category.slug if is_open and active_category else parent.slug

        is_perfume_category = parent.slug in ('perfumes', 'decanter')

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
            traditional_count = scoped_products.filter(is_fractioned=False).count()
            fractioned_count = scoped_products.filter(is_fractioned=True).count()
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
