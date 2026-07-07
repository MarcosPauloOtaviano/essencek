from .models import Cart


MAX_CART_QUANTITY = 99


def _quantity_limit_for(product, variant=None):
    if variant:
        return max(0, min(variant.stock, MAX_CART_QUANTITY))
    if product.is_pre_order:
        return MAX_CART_QUANTITY
    return max(0, min(product.stock, MAX_CART_QUANTITY))


def get_cart(request):
    """Return or create cart for current user/session."""
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        # Merge anonymous cart if exists
        session_key = request.session.session_key
        if session_key:
            try:
                anon_cart = Cart.objects.get(session_key=session_key, user=None)
                for item in anon_cart.items.all():
                    limit = _quantity_limit_for(item.product, item.variant)
                    if limit <= 0:
                        item.delete()
                        continue
                    existing = cart.items.filter(product=item.product, variant=item.variant).first()
                    if existing:
                        existing.quantity = min(existing.quantity + item.quantity, limit)
                        existing.save(update_fields=['quantity'])
                    else:
                        item.quantity = min(item.quantity, limit)
                        item.cart = cart
                        item.save(update_fields=['quantity', 'cart'])
                anon_cart.delete()
            except Cart.DoesNotExist:
                pass
        return cart
    else:
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key
        cart, _ = Cart.objects.get_or_create(session_key=session_key, user=None)
        return cart
