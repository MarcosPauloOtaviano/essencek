from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib import messages
from django.db import transaction
from decimal import Decimal, InvalidOperation
from products.models import Product, ProductVariant
from shipping.utils import calculate_shipping
from .models import CartItem
from .utils import (
    MAX_CART_QUANTITY,
    _quantity_limit_for,
    cart_signature,
    clear_shipping_selection,
    get_cart,
)


def _is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _cart_error(request, message, redirect_to, status=400, **redirect_kwargs):
    if _is_ajax(request):
        return JsonResponse({'error': message}, status=status)
    messages.error(request, message)
    return redirect(redirect_to, **redirect_kwargs)


def _parse_quantity(value, allow_zero=False):
    try:
        quantity = int(value)
    except (TypeError, ValueError):
        raise ValueError('Quantidade inválida.')

    if quantity < 0 or (quantity == 0 and not allow_zero):
        raise ValueError('Quantidade inválida.')
    if quantity > MAX_CART_QUANTITY:
        raise ValueError(f'Quantidade máxima por item: {MAX_CART_QUANTITY}.')
    return quantity


def cart_detail(request):
    cart = get_cart(request)
    items = list(
        cart.items.select_related('product', 'variant').prefetch_related(
            'product__images',
            'product__variants',
        )
    )
    cart._prefetched_objects_cache = {'items': items}
    try:
        selected_shipping_cost = Decimal(str(request.session.get('shipping_cost', '0')))
    except (InvalidOperation, TypeError, ValueError):
        selected_shipping_cost = Decimal('0')
    selected_shipping_service = request.session.get('shipping_service', '')
    if not selected_shipping_service:
        selected_shipping_cost = Decimal('0')
    return render(request, 'cart/cart.html', {
        'cart': cart,
        'items': items,
        'selected_shipping_cost': selected_shipping_cost,
        'selected_shipping_service': selected_shipping_service,
        'cart_total': cart.subtotal + selected_shipping_cost,
    })


@ensure_csrf_cookie
def csrf_token_view(request):
    """Issue a fresh token for quick-add controls rendered on cacheable pages."""
    return JsonResponse({'csrf_token': get_token(request)})


@require_POST
def cart_add(request, product_id):
    with transaction.atomic():
        product = get_object_or_404(
            Product.objects.select_for_update(),
            pk=product_id,
            is_active=True,
        )
        variant = None

        if not product.can_add_to_cart():
            return _cart_error(request, 'Produto indisponível.', 'products:detail', slug=product.slug)

        variant_id = request.POST.get('variant_id')
        if product.is_fractioned and product.has_variants:
            if not variant_id:
                return _cart_error(request, 'Escolha uma variação antes de adicionar ao carrinho.', 'products:detail', slug=product.slug)
            variant = get_object_or_404(
                ProductVariant.objects.select_for_update(),
                pk=variant_id,
                product=product,
                is_active=True,
            )

        try:
            quantity = _parse_quantity(request.POST.get('quantity', 1))
        except ValueError as exc:
            return _cart_error(request, str(exc), 'products:detail', slug=product.slug)

        cart = get_cart(request)
        item = (
            CartItem.objects.select_for_update()
            .filter(cart=cart, product=product, variant=variant)
            .first()
        )
        current_quantity = item.quantity if item else 0
        limit = _quantity_limit_for(product, variant)
        if current_quantity + quantity > limit:
            if limit <= 0:
                message = 'Produto sem estoque para pronta entrega.'
            else:
                message = f'Quantidade indisponível. Estoque atual: {limit}.'
            return _cart_error(request, message, 'products:detail', slug=product.slug)

        if item:
            item.quantity = current_quantity + quantity
            item.save(update_fields=['quantity'])
        else:
            CartItem.objects.create(cart=cart, product=product, variant=variant, quantity=quantity)
        clear_shipping_selection(request)

    if _is_ajax(request):
        return JsonResponse({
            'success': True,
            'cart_count': cart.total_items,
            'message': f'{product.name} adicionado ao carrinho!'
        })

    messages.success(request, f'{product.name} adicionado ao carrinho!')
    if request.POST.get('buy_now'):
        return redirect('orders:checkout')
    return redirect('cart:detail')


@require_POST
def cart_update(request, item_id):
    with transaction.atomic():
        cart = get_cart(request)
        item = get_object_or_404(
            CartItem.objects.select_for_update().select_related('product', 'variant'),
            pk=item_id,
            cart=cart,
        )

        try:
            quantity = _parse_quantity(request.POST.get('quantity', 1), allow_zero=True)
        except ValueError as exc:
            if _is_ajax(request):
                return JsonResponse({
                    'error': str(exc),
                    'current_quantity': item.quantity,
                }, status=400)
            return _cart_error(request, str(exc), 'cart:detail')

        if quantity == 0:
            item.delete()
        else:
            invalid_variant = (
                item.product.is_fractioned
                and item.product.has_variants
                and (not item.variant or not item.variant.is_active)
            )
            if not item.product.can_add_to_cart() or invalid_variant:
                message = 'Este item não está mais disponível nessa quantidade.'
                if _is_ajax(request):
                    return JsonResponse({
                        'error': message,
                        'current_quantity': item.quantity,
                    }, status=409)
                return _cart_error(request, message, 'cart:detail')
            limit = _quantity_limit_for(item.product, item.variant)
            if quantity > limit:
                if limit <= 0:
                    message = 'Produto sem estoque para pronta entrega.'
                else:
                    message = f'Quantidade indisponível. Estoque atual: {limit}.'
                if _is_ajax(request):
                    return JsonResponse({
                        'error': message,
                        'current_quantity': item.quantity,
                        'limit': limit,
                    }, status=400)
                return _cart_error(request, message, 'cart:detail')
            item.quantity = quantity
            item.save(update_fields=['quantity'])
        clear_shipping_selection(request)

    if _is_ajax(request):
        return JsonResponse({
            'success': True,
            'subtotal': float(item.subtotal) if quantity > 0 else 0,
            'subtotal_usd': float(item.subtotal_usd) if quantity > 0 and item.subtotal_usd is not None else None,
            'cart_count': cart.total_items,
            'cart_subtotal': float(cart.subtotal),
            'cart_subtotal_usd': float(cart.subtotal_usd) if cart.subtotal_usd is not None else None,
        })
    return redirect('cart:detail')


@require_POST
def cart_remove(request, item_id):
    with transaction.atomic():
        cart = get_cart(request)
        item = get_object_or_404(
            CartItem.objects.select_for_update(),
            pk=item_id,
            cart=cart,
        )
        item.delete()
        clear_shipping_selection(request)
        messages.success(request, 'Item removido do carrinho.')
    return redirect('cart:detail')


def calculate_shipping_view(request):
    cep = request.GET.get('cep', '').replace('-', '').replace('.', '').strip()
    if not cep or len(cep) != 8:
        return JsonResponse({'error': 'CEP inválido.'}, status=400)

    product_id = request.GET.get('product_id', '').strip()
    cart = None
    if product_id:
        product = get_object_or_404(Product, pk=product_id, is_active=True)
        if not product.can_add_to_cart():
            return JsonResponse({'error': 'Produto indisponível para cálculo de frete.'}, status=409)
        result = calculate_shipping(cep, product=product)
    else:
        cart = get_cart(request)
        if not cart.items.exists():
            return JsonResponse({'error': 'Adicione um produto antes de calcular o frete.'}, status=400)
        result = calculate_shipping(cep, cart=cart)

    if result.get('success') and cart is not None:
        request.session['shipping_cep'] = result['cep']
        request.session['shipping_options'] = result['options']
        request.session['shipping_cart_signature'] = cart_signature(cart)
        request.session.pop('shipping_cost', None)
        request.session.pop('shipping_service', None)
        request.session.pop('shipping_service_code', None)
        request.session.pop('shipping_carrier', None)
        request.session.modified = True
    return JsonResponse(result)


@require_POST
def select_shipping_view(request):
    cart = get_cart(request)
    expected_signature = request.session.get('shipping_cart_signature', '')
    if not expected_signature or expected_signature != cart_signature(cart):
        clear_shipping_selection(request)
        return JsonResponse({'error': 'O carrinho mudou. Calcule o frete novamente.'}, status=409)

    service = request.POST.get('service', '').strip()
    try:
        price = Decimal(str(request.POST.get('price', '')))
    except (InvalidOperation, ValueError):
        return JsonResponse({'error': 'Frete inválido.'}, status=400)

    options = request.session.get('shipping_options') or []
    selected = None
    for option in options:
        try:
            option_price = Decimal(str(option.get('price')))
        except (InvalidOperation, ValueError):
            continue
        if option.get('service') == service and option_price == price:
            selected = option
            break

    if not selected:
        return JsonResponse({'error': 'Opção de frete inválida ou expirada.'}, status=400)

    request.session['shipping_cost'] = str(price)
    request.session['shipping_service'] = selected.get('label') or selected.get('service', '')
    request.session['shipping_service_code'] = selected.get('service', '')
    request.session['shipping_carrier'] = selected.get('carrier', '')
    request.session.modified = True
    return JsonResponse({'success': True, 'shipping_cost': float(price)})
