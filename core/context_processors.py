from .models import StoreSettings
from .services import (
    get_active_exchange_rate,
    get_store_whatsapp_url,
    rate_updated_label,
)


def store_settings(request):
    try:
        settings = StoreSettings.get_settings()
    except Exception:
        settings = None
    try:
        whatsapp_url = get_store_whatsapp_url(settings)
    except Exception:
        whatsapp_url = ''
    return {
        'store_settings': settings,
        'store_whatsapp_url': whatsapp_url,
    }


def exchange_rate(request):
    try:
        rate = get_active_exchange_rate()
    except Exception:
        rate = None
    return {
        'current_exchange_rate': rate,
        'current_exchange_rate_updated_label': rate_updated_label(rate),
    }


def site_navigation(request):
    from django.core.cache import cache
    from products.services import build_main_navigation

    cache_key = 'site_navigation:v1'
    items = cache.get(cache_key)
    if items is None:
        try:
            items = build_main_navigation()
        except Exception:
            items = []
        cache.set(cache_key, items, 300)
    return {'site_navigation': items}
