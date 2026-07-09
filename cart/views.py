from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from decimal import Decimal, InvalidOperation
from products.models import Product, ProductVariant
from shipping.utils import calculate_shipping
from .models import CartItem
from .utils import get_cart, MAX_CART_QUANTITY, _quantity_limit_for
import json


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
    items = cart.items.select_related('product', 'variant').prefetch_related('product__images')
    return render(request, 'cart/cart.html', {'cart': cart, 'items': items})


@require_POST
def cart_add(request, product_id):
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    variant = None

    if not product.can_add_to_cart():
        return _cart_error(request, 'Produto indisponível.', 'products:detail', slug=product.slug)

    variant_id = request.POST.get('variant_id')
    if product.is_fractioned and product.has_variants:
        if not variant_id:
            return _cart_error(request, 'Escolha uma variação antes de adicionar ao carrinho.', 'products:detail', slug=product.slug)
        variant = get_object_or_404(ProductVariant, pk=variant_id, product=product, is_active=True)

    try:
        quantity = _parse_quantity(request.POST.get('quantity', 1))
    except ValueError as exc:
        return _cart_error(request, str(exc), 'products:detail', slug=product.slug)

    cart = get_cart(request)
    item = CartItem.objects.filter(cart=cart, product=product, variant=variant).first()
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
    item = get_object_or_404(CartItem, pk=item_id)
    cart = get_cart(request)

    if item.cart != cart:
        return JsonResponse({'error': 'Acesso negado.'}, status=403)

    try:
        quantity = _parse_quantity(request.POST.get('quantity', 1), allow_zero=True)
    except ValueError as exc:
        return _cart_error(request, str(exc), 'cart:detail')

    if quantity == 0:
        item.delete()
    else:
        limit = _quantity_limit_for(item.product, item.variant)
        if quantity > limit:
            if limit <= 0:
                message = 'Produto sem estoque para pronta entrega.'
            else:
                message = f'Quantidade indisponível. Estoque atual: {limit}.'
            return _cart_error(request, message, 'cart:detail')
        item.quantity = quantity
        item.save(update_fields=['quantity'])

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
    item = get_object_or_404(CartItem, pk=item_id)
    cart = get_cart(request)
    if item.cart == cart:
        item.delete()
        messages.success(request, 'Item removido do carrinho.')
    return redirect('cart:detail')


def calculate_shipping_view(request):
    cep = request.GET.get('cep', '').replace('-', '').replace('.', '').strip()
    cart = get_cart(request)
    if not cep or len(cep) != 8:
        return JsonResponse({'error': 'CEP inválido.'}, status=400)
    result = calculate_shipping(cep, cart)
    if result.get('success'):
        request.session['shipping_cep'] = result['cep']
        request.session['shipping_options'] = result['options']
        request.session.pop('shipping_cost', None)
        request.session.pop('shipping_service', None)
        request.session.modified = True
    return JsonResponse(result)


@require_POST
def select_shipping_view(request):
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
    request.session['shipping_service'] = selected.get('service', '')
    request.session['shipping_carrier'] = selected.get('carrier', '')
    request.session.modified = True
    return JsonResponse({'success': True, 'shipping_cost': float(price)})
