from .models import Cart
from .utils import get_cart_token


def cart_count(request):
    """Return cart item count without creating a session or cart."""
    try:
        if hasattr(request, 'user') and request.user.is_authenticated:
            cart = Cart.objects.filter(user=request.user).first()
        else:
            cart_token = get_cart_token(request) if hasattr(request, 'session') else ''
            if not cart_token:
                return {'cart_count': 0}
            cart = Cart.objects.filter(session_key=cart_token, user=None).first()
        count = cart.total_items if cart else 0
    except Exception:
        count = 0
    return {'cart_count': count}
