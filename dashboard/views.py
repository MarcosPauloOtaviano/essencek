import json
import logging

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User
from core.forms import NextTripForm, StoreSettingsForm
from core.models import StoreSettings, NextTrip
from orders.models import Order, PreOrderRequest
from orders.services import confirm_order_payment
from products.forms import ProductForm, CategoryForm, BrandForm, ProductVariantFormSet
from products.gtin_service import lookup_product_identifier, normalize_gtin
from products.image_downloader import download_and_process_image
from products.image_utils import build_web_product_image
from products.models import Product, Category, ProductImage, Brand
from .services import get_dashboard_summary, get_reports_data

logger = logging.getLogger('products.gtin')


def _save_captured_image(request, product, has_uploaded_images):
    captured_url = request.POST.get('captured_image_url', '').strip()
    if not captured_url:
        return
    image_file = download_and_process_image(captured_url, filename_stem=product.slug or 'produto')
    if not image_file:
        logger.warning('Failed to download captured image from %s for product %s', captured_url, product.pk)
        return
    existing_count = product.images.count()
    is_main = existing_count == 0 and not has_uploaded_images
    ProductImage.objects.create(
        product=product,
        image=image_file,
        is_main=is_main,
        order=0 if is_main else existing_count,
    )
    if is_main:
        product.images.exclude(is_main=True).update(is_main=False)


@staff_member_required(login_url='/conta/entrar/')
def dashboard_home(request):
    now = timezone.now()
    data = get_dashboard_summary(now)
    data['chart_labels'] = json.dumps(data['chart_labels'])
    data['chart_revenue'] = json.dumps(data['chart_revenue'])
    data['now'] = now
    return render(request, 'dashboard/index.html', data)


@staff_member_required(login_url='/conta/entrar/')
def product_list(request):
    products = (
        Product.objects.select_related('category', 'brand_fk')
        .prefetch_related('images', 'variants')
        .order_by('-created_at')
    )
    q = request.GET.get('q', '')
    cat = request.GET.get('category', '')
    status = request.GET.get('status', '')
    if q:
        q_gtin = normalize_gtin(q)
        products = products.filter(
            Q(name__icontains=q) |
            Q(brand__icontains=q) |
            Q(brand_fk__name__icontains=q) |
            Q(gtin__icontains=q_gtin) |
            Q(variants__gtin__icontains=q_gtin)
        ).distinct()
    if cat:
        products = products.filter(category__slug=cat)
    if status:
        products = products.filter(status=status)
    categories = Category.objects.filter(is_active=True)
    return render(request, 'dashboard/products.html', {
        'products': products,
        'categories': categories,
        'status_choices': Product.STATUS_CHOICES,
        'q': q, 'selected_cat': cat, 'selected_status': status,
    })


@staff_member_required(login_url='/conta/entrar/')
def product_add(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        variant_formset = ProductVariantFormSet(request.POST, prefix='variants')
        if form.is_valid() and variant_formset.is_valid():
            product = form.save()
            variant_formset.instance = product
            variant_formset.save()
            images = form.cleaned_data.get('images', [])
            for i, img in enumerate(images):
                image_file = build_web_product_image(img)
                ProductImage.objects.create(
                    product=product,
                    image=image_file,
                    is_main=(i == 0),
                    order=i
                )
            _save_captured_image(request, product, has_uploaded_images=bool(images))
            if product.variants.exists():
                product.has_variants = True
                product.save(update_fields=['has_variants'])
            messages.success(request, f'Produto "{product.name}" criado com sucesso!')
            return redirect('dashboard:product_edit', pk=product.pk)
    else:
        form = ProductForm()
        variant_formset = ProductVariantFormSet(prefix='variants')
    return render(request, 'dashboard/product_form.html', {
        'form': form,
        'variant_formset': variant_formset,
        'title': 'Novo produto',
    })


@staff_member_required(login_url='/conta/entrar/')
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        variant_formset = ProductVariantFormSet(request.POST, instance=product, prefix='variants')
        if form.is_valid() and variant_formset.is_valid():
            product = form.save()
            variant_formset.save()
            images = form.cleaned_data.get('images', [])
            existing_count = product.images.count()
            for i, img in enumerate(images):
                image_file = build_web_product_image(img)
                ProductImage.objects.create(
                    product=product,
                    image=image_file,
                    is_main=(existing_count == 0 and i == 0),
                    order=existing_count + i
                )
            _save_captured_image(request, product, has_uploaded_images=bool(images))
            product.has_variants = product.variants.exists()
            product.save(update_fields=['has_variants'])
            messages.success(request, f'Produto "{product.name}" atualizado!')
            return redirect('dashboard:product_edit', pk=product.pk)
    else:
        form = ProductForm(instance=product)
        variant_formset = ProductVariantFormSet(instance=product, prefix='variants')
    return render(request, 'dashboard/product_form.html', {
        'form': form,
        'variant_formset': variant_formset,
        'product': product,
        'title': f'Editar: {product.name}',
    })


@staff_member_required(login_url='/conta/entrar/')
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        name = product.name
        product.delete()
        messages.success(request, f'Produto "{name}" removido.')
        return redirect('dashboard:products')
    return render(request, 'dashboard/product_confirm_delete.html', {'product': product})


@staff_member_required(login_url='/conta/entrar/')
@require_POST
def image_set_main(request, pk):
    img = get_object_or_404(ProductImage, pk=pk)
    img.is_main = True
    img.save()
    return JsonResponse({'success': True})


@staff_member_required(login_url='/conta/entrar/')
@require_POST
def image_delete(request, pk):
    img = get_object_or_404(ProductImage, pk=pk)
    product_pk = img.product_id
    img.image.delete(save=False)
    img.delete()
    return redirect('dashboard:product_edit', pk=product_pk)


@staff_member_required(login_url='/conta/entrar/')
def order_list(request):
    orders = Order.objects.select_related('customer').order_by('-created_at')
    status = request.GET.get('status', '')
    q = request.GET.get('q', '')
    if status:
        orders = orders.filter(status=status)
    if q:
        orders = orders.filter(
            Q(order_number__icontains=q) |
            Q(customer_name__icontains=q) |
            Q(customer_whatsapp__icontains=q)
        )
    return render(request, 'dashboard/orders.html', {
        'orders': orders,
        'status_choices': Order.STATUS_CHOICES,
        'selected_status': status,
        'q': q,
    })


@staff_member_required(login_url='/conta/entrar/')
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'confirm_payment':
            confirmed = confirm_order_payment(order)
            if confirmed:
                messages.success(request, 'Pagamento confirmado!')
            else:
                messages.info(request, 'Este pagamento já estava confirmado.')
        elif action == 'update_tracking':
            tracking_url = request.POST.get('tracking_url', '').strip()
            if tracking_url:
                try:
                    URLValidator(schemes=['http', 'https'])(tracking_url)
                except ValidationError:
                    messages.error(request, 'Informe um link de rastreio válido começando com http:// ou https://.')
                    return redirect('dashboard:order_detail', pk=order.pk)
            order.tracking_code = request.POST.get('tracking_code', '').strip()
            order.carrier = request.POST.get('carrier', '').strip()
            order.tracking_url = tracking_url
            order.status = Order.STATUS_SHIPPED
            order.shipped_at = timezone.now()
            order.save()
            messages.success(request, 'Rastreamento atualizado!')
        elif action == 'update_status':
            status = request.POST.get('status', order.status)
            valid_statuses = {value for value, _ in Order.STATUS_CHOICES}
            if status not in valid_statuses:
                messages.error(request, 'Status de pedido inválido.')
                return redirect('dashboard:order_detail', pk=order.pk)
            order.status = status
            order.internal_notes = request.POST.get('internal_notes', order.internal_notes)
            order.save()
            messages.success(request, 'Status atualizado!')
        return redirect('dashboard:order_detail', pk=order.pk)
    return render(request, 'dashboard/order_detail.html', {
        'order': order,
        'status_choices': Order.STATUS_CHOICES,
    })


@staff_member_required(login_url='/conta/entrar/')
def customer_list(request):
    customers = User.objects.filter(is_staff=False).order_by('-date_joined')
    q = request.GET.get('q', '')
    if q:
        customers = customers.filter(
            Q(full_name__icontains=q) | Q(email__icontains=q) |
            Q(cpf__icontains=q) | Q(whatsapp__icontains=q)
        )
    return render(request, 'dashboard/customers.html', {'customers': customers, 'q': q})


@staff_member_required(login_url='/conta/entrar/')
def pre_order_list(request):
    pre_orders = PreOrderRequest.objects.select_related('customer', 'product', 'trip').order_by('-created_at')
    return render(request, 'dashboard/pre_orders.html', {'pre_orders': pre_orders})


@staff_member_required(login_url='/conta/entrar/')
def next_trip_edit(request):
    trip = NextTrip.objects.filter(is_active=True).first()
    if request.method == 'POST':
        form = NextTripForm(request.POST, instance=trip)
        if form.is_valid():
            form.save()
            messages.success(request, 'Próxima viagem atualizada!')
            return redirect('dashboard:next_trip')
    else:
        form = NextTripForm(instance=trip)
    return render(request, 'dashboard/next_trip.html', {'form': form, 'trip': trip})


@staff_member_required(login_url='/conta/entrar/')
def store_settings(request):
    store = StoreSettings.get_settings()
    if request.method == 'POST':
        form = StoreSettingsForm(request.POST, request.FILES, instance=store)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configurações salvas!')
            return redirect('dashboard:settings')
    else:
        form = StoreSettingsForm(instance=store)
    return render(request, 'dashboard/settings.html', {'form': form, 'store': store})


@staff_member_required(login_url='/conta/entrar/')
def reports_view(request):
    now = timezone.now()
    data = get_reports_data(now)
    data['chart_cat_labels'] = json.dumps(data['chart_cat_labels'])
    data['chart_cat_data'] = json.dumps(data['chart_cat_data'])
    data['now'] = now
    return render(request, 'dashboard/reports.html', data)


@staff_member_required(login_url='/conta/entrar/')
def category_list(request):
    categories = Category.objects.all().order_by('order', 'name')
    return render(request, 'dashboard/categories.html', {'categories': categories})


@staff_member_required(login_url='/conta/entrar/')
def category_edit(request, pk=None):
    category = get_object_or_404(Category, pk=pk) if pk else None
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES, instance=category)
        if form.is_valid():
            cat = form.save()
            messages.success(request, f'Categoria "{cat.name}" salva!')
            return redirect('dashboard:categories')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'dashboard/category_form.html', {
        'form': form,
        'category': category,
        'title': 'Editar categoria' if category else 'Nova categoria',
    })


@staff_member_required(login_url='/conta/entrar/')
def gtin_lookup(request):
    raw_code = request.GET.get('code', '').strip()
    if not raw_code:
        return JsonResponse({'error': 'Informe o código, nome, marca ou termo do produto.'}, status=400)

    if len(raw_code) > 200:
        return JsonResponse({'error': 'Entrada muito longa.'}, status=400)

    code = normalize_gtin(raw_code)
    logger.info('API gtin_lookup called: raw=%r cleaned=%r by user=%s', raw_code, code, request.user)

    try:
        result = lookup_product_identifier(raw_code)
    except Exception:
        logger.exception('gtin_lookup crashed for raw=%r', raw_code)
        return JsonResponse({
            'found': False,
            'code': code or raw_code,
            'message': 'Erro interno ao consultar o código. Tente novamente.',
        }, status=500)

    if result:
        return JsonResponse({'found': True, 'code': code or raw_code, **result})
    return JsonResponse({
        'found': False,
        'code': code or raw_code,
        'message': 'Produto não encontrado nas bases configuradas. Busque por outro termo ou cadastre manualmente.',
    })


@staff_member_required(login_url='/conta/entrar/')
@require_POST
def image_from_url(request, pk):
    product = get_object_or_404(Product, pk=pk)
    url = request.POST.get('image_url', '').strip()
    if not url:
        return JsonResponse({'error': 'URL não informada.'}, status=400)
    if len(url) > 2048:
        return JsonResponse({'error': 'URL muito longa.'}, status=400)

    image_file = download_and_process_image(url, filename_stem=product.slug or 'produto')
    if not image_file:
        return JsonResponse({'error': 'Não foi possível baixar ou processar a imagem.'}, status=400)

    has_images = product.images.exists()
    img = ProductImage.objects.create(
        product=product,
        image=image_file,
        is_main=not has_images,
        order=product.images.count(),
    )
    return JsonResponse({
        'success': True,
        'image_id': img.pk,
        'image_url': img.display_url,
        'is_main': img.is_main,
    })


@staff_member_required(login_url='/conta/entrar/')
def image_search(request):
    query = request.GET.get('q', '').strip()
    if not query or len(query) < 2:
        return JsonResponse({'error': 'Informe um termo de busca.'}, status=400)
    if len(query) > 200:
        return JsonResponse({'error': 'Termo muito longo.'}, status=400)

    results = _search_product_images(query)
    return JsonResponse({'images': results})


def _search_product_images(query):
    import requests as http_requests

    images = []

    gtin = normalize_gtin(query)
    if gtin and len(gtin) in {8, 12, 13, 14}:
        images.extend(_search_open_facts_images(gtin, http_requests))
        images.extend(_search_cosmos_images(gtin, http_requests))

    if not images:
        images.extend(_search_open_facts_by_name(query, http_requests))

    seen = set()
    unique = []
    for img in images:
        if img['url'] not in seen:
            seen.add(img['url'])
            unique.append(img)
        if len(unique) >= 6:
            break

    return unique


def _search_open_facts_images(code, http_requests):
    results = []
    for base_url, source in [
        ('https://world.openfoodfacts.org', 'Open Food Facts'),
        ('https://world.openbeautyfacts.org', 'Open Beauty Facts'),
    ]:
        try:
            resp = http_requests.get(
                f'{base_url}/api/v2/product/{code}.json',
                timeout=8,
                headers={'User-Agent': 'EssenceK/1.0'},
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            if data.get('status') != 1:
                continue
            product = data.get('product', {})
            for key in ('image_front_url', 'image_url', 'image_small_url'):
                url = product.get(key, '')
                if url:
                    results.append({'url': url, 'source': source, 'label': product.get('product_name', code)})
        except Exception:
            continue
    return results


def _search_cosmos_images(code, http_requests):
    token = getattr(settings, 'COSMOS_API_TOKEN', '')
    if not token:
        return []
    try:
        resp = http_requests.get(
            f'https://api.cosmos.bluesoft.com.br/gtins/{code}',
            timeout=8,
            headers={'X-Cosmos-Token': token, 'User-Agent': 'EssenceK/1.0'},
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        thumb = data.get('thumbnail', '')
        if thumb:
            return [{'url': thumb, 'source': 'Cosmos', 'label': data.get('description', code)}]
    except Exception:
        pass
    return []


def _search_open_facts_by_name(query, http_requests):
    results = []
    try:
        resp = http_requests.get(
            'https://world.openfoodfacts.org/cgi/search.pl',
            params={'search_terms': query, 'search_simple': 1, 'json': 1, 'page_size': 5},
            timeout=8,
            headers={'User-Agent': 'EssenceK/1.0'},
        )
        if resp.status_code == 200:
            data = resp.json()
            for p in data.get('products', [])[:5]:
                url = p.get('image_front_url', '')
                if url:
                    results.append({
                        'url': url,
                        'source': 'Open Food Facts',
                        'label': p.get('product_name', ''),
                    })
    except Exception:
        pass
    try:
        resp = http_requests.get(
            'https://world.openbeautyfacts.org/cgi/search.pl',
            params={'search_terms': query, 'search_simple': 1, 'json': 1, 'page_size': 5},
            timeout=8,
            headers={'User-Agent': 'EssenceK/1.0'},
        )
        if resp.status_code == 200:
            data = resp.json()
            for p in data.get('products', [])[:5]:
                url = p.get('image_front_url', '')
                if url:
                    results.append({
                        'url': url,
                        'source': 'Open Beauty Facts',
                        'label': p.get('product_name', ''),
                    })
    except Exception:
        pass
    return results


# ── Brand CRUD ──────────────────────────────────────────────

@staff_member_required(login_url='/conta/entrar/')
def brand_list(request):
    from django.db.models import Count
    brands = (
        Brand.objects.annotate(product_count=Count('products', filter=Q(products__is_active=True)))
        .order_by('name')
    )
    return render(request, 'dashboard/brands.html', {'brands': brands})


@staff_member_required(login_url='/conta/entrar/')
def brand_edit(request, pk=None):
    brand = get_object_or_404(Brand, pk=pk) if pk else None
    if request.method == 'POST':
        form = BrandForm(request.POST, request.FILES, instance=brand)
        if form.is_valid():
            b = form.save()
            messages.success(request, f'Marca "{b.name}" salva!')
            return redirect('dashboard:brands')
    else:
        form = BrandForm(instance=brand)
    return render(request, 'dashboard/brand_form.html', {
        'form': form,
        'brand': brand,
        'title': 'Editar marca' if brand else 'Nova marca',
    })


@staff_member_required(login_url='/conta/entrar/')
def brand_delete(request, pk):
    brand = get_object_or_404(Brand, pk=pk)
    if request.method == 'POST':
        name = brand.name
        brand.is_active = False
        brand.save()
        messages.success(request, f'Marca "{name}" desativada.')
        return redirect('dashboard:brands')
    return render(request, 'dashboard/brand_confirm_delete.html', {'brand': brand})
