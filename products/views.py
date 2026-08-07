from decimal import Decimal, InvalidOperation

from django.http import Http404, HttpResponsePermanentRedirect
from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Case, DecimalField, F, Prefetch, Q, When
from django.urls import reverse

from .gtin_service import normalize_gtin
from .models import Brand, Product, ProductVariant
from .services import (
    active_category_queryset,
    attach_category_totals,
    build_filter_tree,
    build_breadcrumbs,
    build_collection_cards,
    catalog_url,
    canonical_category_group,
    category_collection_canonical_url,
    category_group_from_legacy_slug,
    category_ids_for_group,
    collection_product_queryset,
    find_category_by_slug,
    get_home_collection,
    get_category_group_label,
    is_category_group,
    valid_sale_q,
)


QUICK_FILTERS = {
    'ofertas': 'Ofertas',
    'destaques': 'Destaques',
    'pronta-entrega': 'Pronta Entrega',
}

SORT_OPTIONS = (
    ('recent', 'Mais recentes'),
    ('featured', 'Destaques primeiro'),
    ('price_asc', 'Menor preco'),
    ('price_desc', 'Maior preco'),
)


def _decimal_query_value(value):
    if not value:
        return None
    try:
        parsed = Decimal(value)
    except (InvalidOperation, TypeError):
        return None
    return parsed if parsed >= 0 else None


def _current_price_expression():
    return Case(
        When(valid_sale_q(), then=F('sale_price')),
        default=F('price'),
        output_field=DecimalField(max_digits=10, decimal_places=2),
    )


def _order_catalog_products(products, selected_sort):
    if selected_sort == 'featured':
        return products.order_by('-is_featured', '-updated_at', '-pk')
    if selected_sort == 'price_asc':
        return products.annotate(catalog_price=_current_price_expression()).order_by('catalog_price', '-pk')
    if selected_sort == 'price_desc':
        return products.annotate(catalog_price=_current_price_expression()).order_by('-catalog_price', '-pk')
    return products.order_by('-created_at', '-pk')


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
    min_price = _decimal_query_value(request.GET.get('min_price', '').strip())
    max_price = _decimal_query_value(request.GET.get('max_price', '').strip())
    selected_sort = request.GET.get('sort', 'recent')
    if selected_sort not in dict(SORT_OPTIONS):
        selected_sort = 'recent'

    collection = get_home_collection(category_key) if category_key else get_home_collection(category_slug)
    collection_subcollections = []

    if collection:
        category_group = ''
    elif category_key:
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

    active_category = None
    if collection:
        collection_subcollections = build_collection_cards(
            list(collection.children.all()), all_categories,
        )
        products = collection_product_queryset(collection, all_categories)
        if category_slug:
            active_category = find_category_by_slug(all_categories, category_slug)
            if active_category:
                products = products.filter(
                    category_id__in=_category_and_children_ids(active_category, all_categories),
                )
            else:
                products = products.none()
    elif category_group:
        category_ids = category_ids_for_group(all_categories, category_group)
        products = products.filter(category_id__in=category_ids) if category_ids else products.none()

    if category_slug and not collection:
        cat = find_category_by_slug(all_categories, category_slug)
        if cat:
            if category_key:
                canonical_url = category_collection_canonical_url(cat)
                if canonical_url:
                    query_string = request.META.get('QUERY_STRING', '')
                    redirect_url = f'{canonical_url}?{query_string}' if query_string else canonical_url
                    return HttpResponsePermanentRedirect(redirect_url)
            active_category = cat
            products = products.filter(
                category_id__in=_category_and_children_ids(cat, all_categories),
            )
        else:
            if category_key:
                raise Http404('Colecao nao encontrada.')
            products = products.none()
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
    if min_price is not None or max_price is not None:
        products = products.annotate(catalog_price=_current_price_expression())
        if min_price is not None:
            products = products.filter(catalog_price__gte=min_price)
        if max_price is not None:
            products = products.filter(catalog_price__lte=max_price)

    products = _order_catalog_products(products, selected_sort)

    paginator = Paginator(products, 24)
    products_page = paginator.get_page(request.GET.get('page', 1))

    filter_categories = [
        category for category in all_categories
        if getattr(category, 'total_active_product_count', 0) > 0
    ]

    filter_tree, filter_active_category, active_root_slug = build_filter_tree(
        filter_categories, category_slug, brand_slug, perfume_type, query,
    )
    active_category = active_category or filter_active_category

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
    elif collection:
        breadcrumb_items = [
            {'label': 'Produtos', 'url': reverse('products:list')},
            {'label': collection.title, 'url': ''},
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
        collection.title if collection else '',
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
        'selected_sort': selected_sort,
        'sort_options': SORT_OPTIONS,
        'selected_min_price': request.GET.get('min_price', '').strip(),
        'selected_max_price': request.GET.get('max_price', '').strip(),
        'active_category': active_category,
        'active_brand_name': active_brand_name,
        'active_root_slug': active_root_slug,
        'perfume_type_label': perfume_type_label,
        'breadcrumb_items': breadcrumb_items,
        'page_title': ' - '.join(page_title_parts) or 'Produtos',
        'all_categories_url': catalog_url(q=query),
        'clear_filters_url': request.path if (collection or category_key) else reverse('products:list'),
        'has_active_filters': any([
            category_slug, brand_slug, perfume_type, status, query, on_sale, featured,
            min_price is not None, max_price is not None, selected_sort != 'recent',
        ]),
        'pagination_query': pagination_params.urlencode(),
        'collection': collection,
        'collection_subcollections': collection_subcollections,
        'filter_action': request.path,
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
