from .models import StoreSettings
from .services import get_active_exchange_rate, rate_updated_label


def store_settings(request):
    try:
        settings = StoreSettings.get_settings()
    except Exception:
        settings = None
    return {'store_settings': settings}


def exchange_rate(request):
    try:
        rate = get_active_exchange_rate()
    except Exception:
        rate = None
    return {
        'current_exchange_rate': rate,
        'current_exchange_rate_updated_label': rate_updated_label(rate),
    }
