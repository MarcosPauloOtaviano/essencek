from .utils import get_cart


def cart_count(request):
    try:
        cart = get_cart(request)
        count = cart.total_items if cart else 0
    except (AttributeError, ValueError, KeyError):
        count = 0
    return {'cart_count': count}
