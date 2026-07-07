from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .models import ExchangeRate


EXCHANGE_RATE_CACHE_KEY = 'exchange_rate_usd_brl'


def _decimal_rate(value):
    try:
        return Decimal(str(value)).quantize(Decimal('0.0001'))
    except (InvalidOperation, TypeError, ValueError):
        return None


def get_active_exchange_rate():
    return ExchangeRate.objects.filter(
        currency_from='USD',
        currency_to='BRL',
        is_active=True,
    ).order_by('-updated_at').first()


def get_usd_brl_rate():
    cached = cache.get(EXCHANGE_RATE_CACHE_KEY)
    if cached:
        return cached

    rate_obj = get_active_exchange_rate()
    if rate_obj:
        cache.set(EXCHANGE_RATE_CACHE_KEY, rate_obj.rate, settings.EXCHANGE_RATE_CACHE_SECONDS)
        return rate_obj.rate

    fallback = _decimal_rate(settings.EXCHANGE_RATE_DEFAULT_USD_BRL) or Decimal('5.5000')
    cache.set(EXCHANGE_RATE_CACHE_KEY, fallback, settings.EXCHANGE_RATE_CACHE_SECONDS)
    return fallback


def fetch_usd_brl_rate():
    response = requests.get(settings.EXCHANGE_RATE_API_URL, timeout=8)
    response.raise_for_status()
    data = response.json()
    payload = data.get('USDBRL', data) if isinstance(data, dict) else {}
    rate = _decimal_rate(payload.get('bid') or payload.get('ask') or payload.get('high'))
    if not rate:
        raise ValueError('A API de cotação não retornou um valor USD/BRL válido.')
    source = payload.get('name') or 'AwesomeAPI USD-BRL'
    return rate, source


def save_usd_brl_rate(rate, source='manual'):
    rate = _decimal_rate(rate)
    if not rate:
        raise ValueError('Cotação USD/BRL inválida.')

    ExchangeRate.objects.filter(currency_from='USD', currency_to='BRL').update(is_active=False)
    obj = ExchangeRate.objects.create(
        currency_from='USD',
        currency_to='BRL',
        rate=rate,
        source=source,
        is_active=True,
    )
    cache.set(EXCHANGE_RATE_CACHE_KEY, obj.rate, settings.EXCHANGE_RATE_CACHE_SECONDS)
    return obj


def update_usd_brl_rate_from_api():
    rate, source = fetch_usd_brl_rate()
    return save_usd_brl_rate(rate, source=source)


def rate_updated_label(rate_obj):
    if not rate_obj:
        return ''
    local_time = timezone.localtime(rate_obj.updated_at)
    return local_time.strftime('%d/%m/%Y às %H:%M')
