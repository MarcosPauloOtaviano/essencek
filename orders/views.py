from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from decimal import Decimal, InvalidOperation
from cart.utils import get_cart
from core.models import ExchangeRate
from .models import Order, OrderItem
from .forms import CheckoutForm
from .services import order_queryset_for_user


def _session_decimal(request, key, default='0'):
    try:
        return Decimal(str(request.session.get(key, default)))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _cart_validation_errors(items):
    errors = []
    for item in items:
        product = item.product
        if not product or not product.can_add_to_cart():
            errors.append(f'{item.product.name if item.product else "Produto"} não está disponível.')
            continue
        if item.variant and item.quantity > item.variant.stock:
            errors.append(f'Estoque insuficiente para {product.name} - {item.variant.name}. Disponível: {item.variant.stock}.')
        elif not product.is_pre_order and not item.variant and item.quantity > product.stock:
            errors.append(f'Estoque insuficiente para {product.name}. Disponível: {product.stock}.')
    return errors


@login_required
def checkout(request):
    cart = get_cart(request)
    items = cart.items.select_related('product', 'variant').prefetch_related('product__images')

    if not items.exists():
        messages.warning(request, 'Seu carrinho está vazio.')
        return redirect('cart:detail')

    stock_errors = _cart_validation_errors(items)
    if stock_errors:
        for error in stock_errors:
            messages.error(request, error)
        return redirect('cart:detail')

    user = request.user
    initial = {
        'customer_name': user.full_name or user.get_full_name(),
        'customer_email': user.email,
        'customer_whatsapp': user.whatsapp,
        'address': user.address,
        'address_number': user.address_number,
        'address_complement': user.address_complement,
        'neighborhood': user.neighborhood,
        'city': user.city,
        'state': user.state,
        'cep': user.cep,
    }

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                data = form.cleaned_data
                is_pickup = data.get('shipping_method') == 'pickup'
                shipping_cost = Decimal('0') if is_pickup else _session_decimal(request, 'shipping_cost')
                subtotal = cart.subtotal
                total = subtotal + shipping_cost
                exchange_rate = ExchangeRate.get_usd_brl()
                subtotal_usd = cart.subtotal_usd
                total_usd = (total / exchange_rate).quantize(Decimal('0.01')) if exchange_rate else subtotal_usd

                order = Order.objects.create(
                    customer=user,
                    customer_name=data['customer_name'],
                    customer_email=data['customer_email'],
                    customer_whatsapp=data['customer_whatsapp'],
                    address=data['address'],
                    address_number=data['address_number'],
                    address_complement=data.get('address_complement', ''),
                    neighborhood=data.get('neighborhood', ''),
                    city=data['city'],
                    state=data['state'],
                    cep=data['cep'],
                    subtotal=subtotal,
                    shipping_cost=shipping_cost,
                    total=total,
                    subtotal_usd=subtotal_usd,
                    total_usd=total_usd,
                    exchange_rate=exchange_rate,
                    shipping_service='Retirada na loja' if is_pickup else request.session.get('shipping_service', ''),
                    payment_method=data['payment_method'],
                    customer_notes=data.get('customer_notes', ''),
                    status=Order.STATUS_AWAITING_PAYMENT,
                )

                for item in items:
                    item_status = 'pre_order' if item.product.is_pre_order else 'ready'
                    OrderItem.objects.create(
                        order=order,
                        product=item.product,
                        variant=item.variant,
                        product_name=item.product.name,
                        product_brand=item.product.display_brand,
                        unit_price=item.unit_price,
                        unit_price_usd=item.unit_price_usd,
                        quantity=item.quantity,
                        variant_name=item.variant.name if item.variant else '',
                        variant_volume_ml=item.variant.volume_ml if item.variant else None,
                        product_category=item.product.category.name if item.product.category else '',
                        is_pre_order=item.product.is_pre_order,
                        item_status=item_status,
                    )

                # Clear cart
                cart.items.all().delete()
                for key in ('shipping_cost', 'shipping_service', 'shipping_carrier', 'shipping_cep', 'shipping_options'):
                    request.session.pop(key, None)

                return redirect('orders:success', order_number=order.order_number)
    else:
        form = CheckoutForm(initial=initial)

    return render(request, 'checkout/checkout.html', {
        'form': form,
        'cart': cart,
        'items': items,
        'payment_is_simulated': getattr(settings, 'PAYMENT_SANDBOX', True),
    })


@login_required
def order_success(request, order_number):
    order = get_object_or_404(order_queryset_for_user(request.user), order_number=order_number)
    return render(request, 'checkout/success.html', {'order': order})
