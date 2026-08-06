import secrets
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.urls import reverse
from django.utils.crypto import constant_time_compare
from decimal import Decimal, InvalidOperation
from cart.models import Cart
from cart.utils import cart_signature, clear_shipping_selection, get_cart
from core.models import ExchangeRate
from products.models import Product, ProductVariant
from .models import Order, OrderItem
from .forms import CheckoutForm
from .services import build_order_whatsapp_url, order_queryset_for_user


CHECKOUT_TOKEN_SESSION_KEY = 'essencek_checkout_token'
CHECKOUT_INTERNAL_PREFIX = 'checkout_token:'


class CheckoutValidationError(Exception):
    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__('; '.join(self.errors))


def _session_decimal(request, key, default='0'):
    try:
        return Decimal(str(request.session.get(key, default)))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _cart_validation_errors(items):
    errors = []
    for item in items:
        product = item.product
        if not product or not product.is_active or product.status == Product.STATUS_OUT_OF_STOCK:
            errors.append(f'{item.product.name if item.product else "Produto"} não está disponível.')
            continue
        if product.is_fractioned and product.has_variants and not item.variant:
            errors.append(f'Escolha uma variação válida para {product.name}.')
        elif item.variant and (not item.variant.is_active or item.variant.product_id != product.pk):
            errors.append(f'A variação escolhida para {product.name} não está disponível.')
        elif item.variant and not product.is_pre_order and item.quantity > item.variant.stock:
            errors.append(f'Estoque insuficiente para {product.name} - {item.variant.name}. Disponível: {item.variant.stock}.')
        elif not product.is_pre_order and not item.variant and item.quantity > product.stock:
            errors.append(f'Estoque insuficiente para {product.name}. Disponível: {product.stock}.')
    return errors


def _new_checkout_token(request):
    token = secrets.token_urlsafe(24)
    request.session[CHECKOUT_TOKEN_SESSION_KEY] = token
    request.session.modified = True
    return token


def _selected_shipping_cost(request):
    return _session_decimal(request, 'shipping_cost') if request.session.get('shipping_service') else Decimal('0')


def _whatsapp_redirect(order, auto_open=False):
    url = reverse('orders:whatsapp', kwargs={'order_number': order.order_number})
    return redirect(f'{url}?open=1' if auto_open else url)


def _checkout_completion_redirect(order, auto_open=False):
    if order.payment_method == Order.PAYMENT_WHATSAPP:
        return _whatsapp_redirect(order, auto_open=auto_open)
    return redirect('orders:success', order_number=order.order_number)


@login_required
def checkout(request):
    cart = get_cart(request)
    items = list(
        cart.items.select_related('product', 'variant').prefetch_related('product__images')
    )
    cart._prefetched_objects_cache = {'items': items}

    submitted_token = request.POST.get('checkout_token', '') if request.method == 'POST' else ''
    expected_token = request.session.get(CHECKOUT_TOKEN_SESSION_KEY, '')
    if (
        submitted_token
        and expected_token
        and constant_time_compare(submitted_token, expected_token)
    ):
        existing_order = Order.objects.filter(
            customer=request.user,
            internal_notes=f'{CHECKOUT_INTERNAL_PREFIX}{submitted_token}',
        ).first()
        if existing_order:
            return _checkout_completion_redirect(existing_order, auto_open=True)

    if not items:
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
            data = form.cleaned_data
            checkout_token = data['checkout_token']
            if not expected_token or not constant_time_compare(checkout_token, expected_token):
                form.add_error(None, 'Esta sessão de checkout expirou. Recarregue a página e tente novamente.')
            else:
                marker = f'{CHECKOUT_INTERNAL_PREFIX}{checkout_token}'
                try:
                    with transaction.atomic():
                        order = (
                            Order.objects.select_for_update()
                            .filter(customer=user, internal_notes=marker)
                            .first()
                        )
                        if order is None:
                            locked_cart = Cart.objects.select_for_update().get(pk=cart.pk, user=user)
                            locked_items = list(
                                locked_cart.items.select_related('product', 'variant', 'product__category')
                                .order_by('pk')
                            )
                            if not locked_items:
                                concurrent_order = Order.objects.filter(
                                    customer=user,
                                    internal_notes=marker,
                                ).first()
                                if concurrent_order:
                                    clear_shipping_selection(request)
                                    request.session.pop(CHECKOUT_TOKEN_SESSION_KEY, None)
                                    request.session['last_checkout_order'] = concurrent_order.order_number
                                    request.session.modified = True
                                    return _checkout_completion_redirect(concurrent_order, auto_open=True)
                                raise CheckoutValidationError(['Seu carrinho está vazio.'])

                            product_ids = {item.product_id for item in locked_items}
                            variant_ids = {item.variant_id for item in locked_items if item.variant_id}
                            list(Product.objects.select_for_update().filter(pk__in=product_ids))
                            list(ProductVariant.objects.select_for_update().filter(pk__in=variant_ids))
                            locked_items = list(
                                locked_cart.items.select_related('product', 'variant', 'product__category')
                                .order_by('pk')
                            )

                            validation_errors = _cart_validation_errors(locked_items)
                            if validation_errors:
                                raise CheckoutValidationError(validation_errors)

                            is_pickup = data.get('shipping_method') == 'pickup'
                            if is_pickup:
                                shipping_cost = Decimal('0')
                                shipping_service = 'Retirada na loja'
                            else:
                                shipping_cost = _selected_shipping_cost(request)
                                shipping_service = request.session.get('shipping_service', '')
                                selected_cep = ''.join(char for char in request.session.get('shipping_cep', '') if char.isdigit())
                                checkout_cep = ''.join(char for char in data.get('cep', '') if char.isdigit())
                                expected_signature = request.session.get('shipping_cart_signature', '')
                                current_signature = cart_signature(locked_cart, locked_items)
                                shipping_errors = []
                                if not shipping_service:
                                    shipping_errors.append('Calcule e selecione o frete no carrinho antes de finalizar.')
                                if selected_cep != checkout_cep:
                                    shipping_errors.append('O CEP do checkout é diferente do CEP usado no cálculo do frete.')
                                if not expected_signature or expected_signature != current_signature:
                                    shipping_errors.append('O carrinho mudou depois do cálculo do frete. Calcule novamente.')
                                if shipping_errors:
                                    raise CheckoutValidationError(shipping_errors)

                            subtotal = sum(item.subtotal for item in locked_items)
                            total = subtotal + shipping_cost
                            exchange_rate = ExchangeRate.get_usd_brl()
                            subtotal_usd_values = [item.subtotal_usd for item in locked_items]
                            subtotal_usd = (
                                None if any(value is None for value in subtotal_usd_values)
                                else sum(subtotal_usd_values, Decimal('0'))
                            )
                            total_usd = (
                                (total / exchange_rate).quantize(Decimal('0.01'))
                                if exchange_rate else subtotal_usd
                            )

                            whatsapp_checkout_only = getattr(settings, 'WHATSAPP_CHECKOUT_ONLY', True)
                            order = Order.objects.create(
                                customer=user,
                                customer_name=data['customer_name'],
                                customer_email=data['customer_email'],
                                customer_whatsapp=data['customer_whatsapp'],
                                address='' if is_pickup else data['address'],
                                address_number='' if is_pickup else data['address_number'],
                                address_complement='' if is_pickup else data.get('address_complement', ''),
                                neighborhood='' if is_pickup else data.get('neighborhood', ''),
                                city='' if is_pickup else data['city'],
                                state='' if is_pickup else data['state'],
                                cep='' if is_pickup else data['cep'],
                                subtotal=subtotal,
                                shipping_cost=shipping_cost,
                                total=total,
                                subtotal_usd=subtotal_usd,
                                total_usd=total_usd,
                                exchange_rate=exchange_rate,
                                shipping_service=shipping_service,
                                payment_method=(
                                    Order.PAYMENT_WHATSAPP
                                    if whatsapp_checkout_only else data['payment_method']
                                ),
                                customer_notes=data.get('customer_notes', ''),
                                internal_notes=marker,
                                status=(
                                    Order.STATUS_AWAITING_CONTACT
                                    if whatsapp_checkout_only else Order.STATUS_AWAITING_PAYMENT
                                ),
                            )

                            OrderItem.objects.bulk_create([
                                OrderItem(
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
                                    item_status=(
                                        'pre_order' if item.product.is_pre_order
                                        else ('awaiting' if whatsapp_checkout_only else 'ready')
                                    ),
                                )
                                for item in locked_items
                            ])
                            locked_cart.items.all().delete()

                    clear_shipping_selection(request)
                    request.session.pop(CHECKOUT_TOKEN_SESSION_KEY, None)
                    request.session['last_checkout_order'] = order.order_number
                    request.session.modified = True
                    return _checkout_completion_redirect(order, auto_open=True)
                except CheckoutValidationError as exc:
                    for error in exc.errors:
                        form.add_error(None, error)
    else:
        initial['checkout_token'] = _new_checkout_token(request)
        form = CheckoutForm(initial=initial)

    selected_shipping_cost = _selected_shipping_cost(request)
    return render(request, 'checkout/checkout.html', {
        'form': form,
        'cart': cart,
        'items': items,
        'selected_shipping_cost': selected_shipping_cost,
        'selected_shipping_service': request.session.get('shipping_service', ''),
        'checkout_total': cart.subtotal + selected_shipping_cost,
        'whatsapp_checkout_only': getattr(settings, 'WHATSAPP_CHECKOUT_ONLY', True),
        'payment_is_simulated': getattr(settings, 'PAYMENT_SANDBOX', True),
    })


@login_required
def order_whatsapp(request, order_number):
    order = get_object_or_404(
        order_queryset_for_user(request.user).prefetch_related('items'),
        order_number=order_number,
    )
    whatsapp_url = build_order_whatsapp_url(order)
    return render(request, 'checkout/whatsapp.html', {
        'order': order,
        'whatsapp_url': whatsapp_url,
        'whatsapp_message': order.whatsapp_message,
        'auto_open': request.GET.get('open') == '1',
    })


@login_required
def order_success(request, order_number):
    order = get_object_or_404(order_queryset_for_user(request.user), order_number=order_number)
    if order.payment_method == Order.PAYMENT_WHATSAPP:
        return _whatsapp_redirect(order)
    return render(request, 'checkout/success.html', {'order': order})
