from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.urls import reverse

from .gtin_service import normalize_gtin
from .models import Brand, Product, ProductVariant
from .services import (
    active_category_queryset,
    attach_category_totals,
    build_filter_tree,
    build_breadcrumbs,
    catalog_url,
    canonical_category_group,
    category_group_from_legacy_slug,
    category_ids_for_group,
    find_category_by_slug,
    get_category_group_label,
    is_category_group,
    valid_sale_q,
)


QUICK_FILTERS = {
    'ofertas': 'Ofertas',
    'destaques': 'Destaques',
    'pronta-entrega': 'Pronta Entrega',
}


def _category_and_children_ids(category, categories):
    category_ids = {category.pk}
    changed = True
    while changed:
        changed = False
        for candidate in categories:
            if candidate.parent_id in category_ids and candidate.pk not in category_ids:
                category_ids.add(candidate.pk)
                changed = True
    return sorted(category_ids)


def product_list(request, category_key='', quick_filter=''):
    products = (
        Product.objects.filter(is_active=True)
        .select_related('category', 'brand_fk')
        .prefetch_related('images', 'variants')
    )

    query = request.GET.get('q', '').strip()[:100]
    category_slug = request.GET.get('category', '')
    category_group = canonical_category_group(request.GET.get('group', ''))
    status = request.GET.get('status', '')
    on_sale = request.GET.get('on_sale', '')
    featured = request.GET.get('featured', '')
    brand_slug = request.GET.get('brand', '')
    perfume_type = request.GET.get('perfume_type', '')

    if category_key:
        if is_category_group(category_key):
            category_group = canonical_category_group(category_key)
            category_slug = ''
        else:
            category_slug = category_key
            category_group = ''

    if not category_group:
        legacy_category_group = category_group_from_legacy_slug(category_slug)
        if legacy_category_group:
            category_group = legacy_category_group
            category_slug = ''

    if quick_filter == 'ofertas':
        on_sale = '1'
    elif quick_filter == 'destaques':
        featured = '1'
    elif quick_filter == 'pronta-entrega':
        status = Product.STATUS_AVAILABLE

    if query:
        query_gtin = normalize_gtin(query)
        search_filter = (
            Q(name__icontains=query)
            | Q(brand__icontains=query)
            | Q(brand_fk__name__icontains=query)
        )
        if query_gtin:
            search_filter |= Q(gtin__icontains=query_gtin) | Q(variants__gtin__icontains=query_gtin)
        products = products.filter(search_filter).distinct()

    all_categories = attach_category_totals(active_category_queryset())

    if category_group:
        category_ids = category_ids_for_group(all_categories, category_group)
        products = products.filter(category_id__in=category_ids) if category_ids else products.none()

    if category_slug:
        cat = find_category_by_slug(all_categories, category_slug)
        if cat:
            products = products.filter(
                category_id__in=_category_and_children_ids(cat, all_categories),
            )
        else:
            products = products.filter(category__slug__iexact=category_slug)
    if brand_slug:
        products = products.filter(
            Q(brand_fk__slug=brand_slug)
            | Q(brand__iexact=brand_slug.replace('-', ' '))
        ).distinct()
    if perfume_type == 'tradicional':
        products = products.filter(is_fractioned=False)
    elif perfume_type == 'fracionado':
        products = products.filter(is_fractioned=True)
    if status:
        products = products.filter(status=status)
    if on_sale:
        products = products.filter(valid_sale_q())
    if featured:
        products = products.filter(is_featured=True)

    paginator = Paginator(products, 24)
    products_page = paginator.get_page(request.GET.get('page', 1))

    filter_categories = [
        category for category in all_categories
        if getattr(category, 'total_active_product_count', 0) > 0
    ]

    filter_tree, active_category, active_root_slug = build_filter_tree(
        filter_categories, category_slug, brand_slug, perfume_type, query,
    )

    active_brand = Brand.objects.filter(slug=brand_slug, is_active=True).first() if brand_slug else None
    active_brand_name = (
        active_brand.name if active_brand
        else (brand_slug.replace('-', ' ').title() if brand_slug else '')
    )
    perfume_type_label = ''
    if perfume_type == 'tradicional':
        perfume_type_label = 'Tradicional / lacrado'
    elif perfume_type == 'fracionado':
        perfume_type_label = 'Fracionado / decanter'

    if quick_filter in QUICK_FILTERS:
        breadcrumb_items = [
            {'label': 'Produtos', 'url': reverse('products:list')},
            {'label': QUICK_FILTERS[quick_filter], 'url': ''},
        ]
    elif category_group:
        breadcrumb_items = [
            {'label': 'Produtos', 'url': reverse('products:list')},
            {'label': get_category_group_label(category_group), 'url': ''},
        ]
    else:
        breadcrumb_items = build_breadcrumbs(
            active_category, active_brand_name, perfume_type_label, category_slug, brand_slug,
        )

    page_title_parts = [p for p in [
        QUICK_FILTERS.get(quick_filter, ''),
        get_category_group_label(category_group) if category_group else '',
        active_category.name if active_category else '',
        active_brand_name,
        perfume_type_label,
    ] if p]

    pagination_params = request.GET.copy()
    pagination_params.pop('page', None)

    return render(request, 'products/list.html', {
        'products': products_page,
        'filter_tree': filter_tree,
        'status_choices': Product.STATUS_CHOICES,
        'query': query,
        'selected_category': category_slug,
        'selected_category_group': category_group,
        'selected_status': status,
        'selected_brand': brand_slug,
        'selected_perfume_type': perfume_type,
        'active_category': active_category,
        'active_brand_name': active_brand_name,
        'active_root_slug': active_root_slug,
        'perfume_type_label': perfume_type_label,
        'breadcrumb_items': breadcrumb_items,
        'page_title': ' - '.join(page_title_parts) or 'Produtos',
        'all_categories_url': catalog_url(q=query),
        'clear_filters_url': reverse('products:list'),
        'pagination_query': pagination_params.urlencode(),
    })


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related('category', 'brand_fk').prefetch_related(
            'images',
            Prefetch(
                'variants',
                queryset=ProductVariant.objects.filter(is_active=True).order_by(
                    'order', 'volume_ml', 'name',
                ),
            ),
        ),
        slug=slug,
        is_active=True,
    )
    images = list(product.images.all())
    variants = []
    if product.is_fractioned and product.has_variants:
        variants = list(product.variants.all())
    first_variant = next(
        (variant for variant in variants if product.is_pre_order or variant.stock > 0),
        None,
    )
    related = (
        Product.objects.filter(category=product.category, is_active=True)
        .select_related('category', 'brand_fk')
        .prefetch_related('images', 'variants')
        .exclude(pk=product.pk)[:4]
    )

    return render(request, 'products/detail.html', {
        'product': product,
        'images': images,
        'variants': variants,
        'first_variant': first_variant,
        'product_available': product.can_add_to_cart(),
        'related': related,
    })
