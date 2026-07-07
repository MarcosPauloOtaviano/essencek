from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q
from django.urls import reverse

from .gtin_service import normalize_gtin
from .models import Brand, Product, Category
from .services import build_filter_tree, build_breadcrumbs, catalog_url


def product_list(request):
    products = (
        Product.objects.filter(is_active=True)
        .select_related('category', 'brand_fk')
        .prefetch_related('images', 'variants')
    )

    query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '')
    status = request.GET.get('status', '')
    on_sale = request.GET.get('on_sale', '')
    featured = request.GET.get('featured', '')
    brand_slug = request.GET.get('brand', '')
    volume = request.GET.get('volume', '')
    try:
        selected_volume_ml = int(volume) if volume else None
    except (TypeError, ValueError):
        selected_volume_ml = None

    if query:
        query_gtin = normalize_gtin(query)
        products = products.filter(
            Q(name__icontains=query)
            | Q(brand__icontains=query)
            | Q(brand_fk__name__icontains=query)
            | Q(gtin__icontains=query_gtin)
            | Q(variants__gtin__icontains=query_gtin)
        ).distinct()
    if category_slug:
        cat = Category.objects.filter(slug=category_slug, is_active=True).first()
        if cat:
            child_ids = list(cat.children.filter(is_active=True).values_list('pk', flat=True))
            products = products.filter(category__in=[cat.pk, *child_ids])
        else:
            products = products.filter(category__slug=category_slug)
    if brand_slug:
        products = products.filter(
            Q(brand_fk__slug=brand_slug)
            | Q(brand__iexact=brand_slug.replace('-', ' '))
        ).distinct()
    if selected_volume_ml:
        products = products.filter(
            variants__volume_ml=selected_volume_ml, variants__is_active=True,
        ).distinct()
    if status:
        products = products.filter(status=status)
    if on_sale:
        products = products.filter(is_on_sale=True)
    if featured:
        products = products.filter(is_featured=True)

    paginator = Paginator(products, 24)
    products_page = paginator.get_page(request.GET.get('page', 1))

    all_categories = list(
        Category.objects.filter(is_active=True)
        .select_related('parent').order_by('order', 'name')
    )

    filter_tree, active_category, active_root_slug = build_filter_tree(
        all_categories, category_slug, brand_slug, selected_volume_ml, query,
    )

    active_brand = Brand.objects.filter(slug=brand_slug, is_active=True).first() if brand_slug else None
    active_brand_name = (
        active_brand.name if active_brand
        else (brand_slug.replace('-', ' ').title() if brand_slug else '')
    )
    selected_volume_label = f'{selected_volume_ml}ml' if selected_volume_ml else ''

    breadcrumb_items = build_breadcrumbs(
        active_category, active_brand_name, selected_volume_label, category_slug, brand_slug,
    )

    page_title_parts = [p for p in [
        active_category.name if active_category else '',
        active_brand_name,
        selected_volume_label,
    ] if p]

    pagination_params = request.GET.copy()
    pagination_params.pop('page', None)

    return render(request, 'products/list.html', {
        'products': products_page,
        'filter_tree': filter_tree,
        'status_choices': Product.STATUS_CHOICES,
        'query': query,
        'selected_category': category_slug,
        'selected_status': status,
        'selected_brand': brand_slug,
        'selected_volume': volume,
        'active_category': active_category,
        'active_brand_name': active_brand_name,
        'active_root_slug': active_root_slug,
        'selected_volume_label': selected_volume_label,
        'breadcrumb_items': breadcrumb_items,
        'page_title': ' - '.join(page_title_parts) or 'Produtos',
        'all_categories_url': catalog_url(q=query),
        'clear_filters_url': reverse('products:list'),
        'pagination_query': pagination_params.urlencode(),
    })


def product_detail(request, slug):
    product = get_object_or_404(Product.objects.select_related('category', 'brand_fk'), slug=slug, is_active=True)
    images = product.images.all()
    variants = product.variants.filter(is_active=True).order_by('order', 'volume_ml', 'name')
    first_variant = variants.first()
    related = Product.objects.filter(
        category=product.category, is_active=True
    ).exclude(pk=product.pk)[:4]

    return render(request, 'products/detail.html', {
        'product': product,
        'images': images,
        'variants': variants,
        'first_variant': first_variant,
        'related': related,
    })
