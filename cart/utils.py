import hashlib
import uuid

from django.db import transaction

from .models import Cart


MAX_CART_QUANTITY = 99
CART_SESSION_TOKEN_KEY = 'essencek_cart_token'


def _quantity_limit_for(product, variant=None):
    if product.is_pre_order:
        return MAX_CART_QUANTITY
    if variant:
        return max(0, min(variant.stock, MAX_CART_QUANTITY))
    return max(0, min(product.stock, MAX_CART_QUANTITY))


def get_cart_token(request, create=False):
    token = request.session.get(CART_SESSION_TOKEN_KEY, '')
    if isinstance(token, str) and len(token) == 32:
        try:
            int(token, 16)
        except ValueError:
            token = ''
        else:
            return token

    if not create:
        return ''

    token = uuid.uuid4().hex
    request.session[CART_SESSION_TOKEN_KEY] = token
    request.session.modified = True
    return token


def cart_signature(cart, items=None):
    if items is None:
        items = cart.items.order_by('product_id', 'variant_id').values_list(
            'product_id', 'variant_id', 'quantity',
        )
    else:
        items = sorted(
            ((item.product_id, item.variant_id, item.quantity) for item in items),
            key=lambda value: (value[0], value[1] or 0),
        )
    payload = '|'.join(f'{product_id}:{variant_id or 0}:{quantity}' for product_id, variant_id, quantity in items)
    return hashlib.sha256(payload.encode('ascii')).hexdigest()


def clear_shipping_selection(request):
    for key in (
        'shipping_cost',
        'shipping_service',
        'shipping_service_code',
        'shipping_carrier',
        'shipping_cep',
        'shipping_options',
        'shipping_cart_signature',
    ):
        request.session.pop(key, None)
    request.session.modified = True


def _merge_cart_items(target, source):
    for item in source.items.select_related('product', 'variant'):
        existing = target.items.filter(product=item.product, variant=item.variant).first()
        limit = _quantity_limit_for(item.product, item.variant)
        if limit <= 0:
            item.delete()
            continue
        combined = item.quantity + (existing.quantity if existing else 0)
        quantity = min(combined, limit)
        if existing:
            existing.quantity = quantity
            existing.save(update_fields=['quantity'])
            item.delete()
        else:
            item.quantity = quantity
            item.cart = target
            item.save(update_fields=['quantity', 'cart'])
    source.delete()


def _get_locked_cart(request):
    """Return or create a cart while the caller owns a database transaction."""
    legacy_session_key = request.session.session_key
    token = get_cart_token(request, create=True)

    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        cart = Cart.objects.select_for_update().get(pk=cart.pk)
        candidate_keys = {token}
        if legacy_session_key and len(legacy_session_key) <= 40:
            candidate_keys.add(legacy_session_key)
        anonymous_carts = list(
            Cart.objects.select_for_update()
            .filter(session_key__in=candidate_keys, user=None)
            .exclude(pk=cart.pk)
        )
        for anonymous_cart in anonymous_carts:
            _merge_cart_items(cart, anonymous_cart)
        return cart

    carts = list(
        Cart.objects.select_for_update()
        .filter(session_key=token, user=None)
        .order_by('-updated_at')
    )
    cart = carts[0] if carts else None
    for duplicate in carts[1:]:
        _merge_cart_items(cart, duplicate)

    if cart is None and legacy_session_key and len(legacy_session_key) <= 40:
        cart = (
            Cart.objects.select_for_update()
            .filter(session_key=legacy_session_key, user=None)
            .order_by('-updated_at')
            .first()
        )
        if cart:
            cart.session_key = token
            cart.save(update_fields=['session_key', 'updated_at'])
    if cart is None:
        cart = Cart.objects.create(session_key=token, user=None)
    return cart


def get_cart(request, *, for_update=False):
    """Return or create the current cart, locking it when a mutation needs it."""
    if for_update:
        if not transaction.get_connection().in_atomic_block:
            raise RuntimeError('get_cart(for_update=True) requer uma transacao ativa.')
        return _get_locked_cart(request)

    with transaction.atomic():
        return _get_locked_cart(request)
