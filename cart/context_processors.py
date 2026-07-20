from .models import Cart


def cart_count(request):
    """Return cart item count without creating a session or cart."""
    try:
        if hasattr(request, 'user') and request.user.is_authenticated:
            cart = Cart.objects.filter(user=request.user).first()
        else:
            session_key = request.session.session_key if hasattr(request, 'session') else None
            if not session_key:
                return {'cart_count': 0}
            cart = Cart.objects.filter(session_key=session_key, user=None).first()
        count = cart.total_items if cart else 0
    except Exception:
        count = 0
    return {'cart_count': count}
