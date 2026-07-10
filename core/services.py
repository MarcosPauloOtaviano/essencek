from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .models import ExchangeRate


DEFAULT_EXCHANGE_PAIR = 'USD-BRL'


def _decimal_rate(value):
    try:
        return Decimal(str(value)).quantize(Decimal('0.0001'))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _normalize_pair(pair):
    normalized = str(pair or '').strip().upper().replace('_', '-').replace('/', '-')
    if '-' not in normalized:
        normalized = f'{normalized[:3]}-{normalized[3:]}'
    parts = [part for part in normalized.split('-', 1) if part]
    if len(parts) != 2 or not all(len(part) == 3 for part in parts):
        raise ValueError(f'Par de moedas inválido: {pair}')
    return f'{parts[0]}-{parts[1]}'


def _pair_parts(pair):
    normalized = _normalize_pair(pair)
    return normalized.split('-', 1)


def _pair_payload_key(pair):
    return _normalize_pair(pair).replace('-', '')


def _cache_key(currency_from, currency_to):
    return f'exchange_rate_{currency_from.lower()}_{currency_to.lower()}'


def get_active_exchange_rate(currency_from='USD', currency_to='BRL'):
    return ExchangeRate.objects.filter(
        currency_from=currency_from,
        currency_to=currency_to,
        is_active=True,
    ).order_by('-updated_at').first()


def get_usd_brl_rate():
    cached = cache.get(_cache_key('USD', 'BRL'))
    if cached:
        return cached

    rate_obj = get_active_exchange_rate('USD', 'BRL')
    if rate_obj:
        cache.set(_cache_key('USD', 'BRL'), rate_obj.rate, settings.EXCHANGE_RATE_CACHE_SECONDS)
        return rate_obj.rate

    fallback = _decimal_rate(settings.EXCHANGE_RATE_DEFAULT_USD_BRL) or Decimal('5.5000')
    cache.set(_cache_key('USD', 'BRL'), fallback, settings.EXCHANGE_RATE_CACHE_SECONDS)
    return fallback


def _exchange_rate_url(pairs):
    normalized_pairs = [_normalize_pair(pair) for pair in pairs]
    if normalized_pairs == [DEFAULT_EXCHANGE_PAIR]:
        return settings.EXCHANGE_RATE_API_URL
    return settings.EXCHANGE_RATE_API_BASE_URL.format(pairs=','.join(normalized_pairs))


def fetch_exchange_rates(pairs=None):
    normalized_pairs = [_normalize_pair(pair) for pair in (pairs or settings.EXCHANGE_RATE_PAIRS)]
    response = requests.get(_exchange_rate_url(normalized_pairs), timeout=8)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError('A API de cotação retornou um formato inválido.')

    results = {}
    for pair in normalized_pairs:
        currency_from, currency_to = _pair_parts(pair)
        payload = data.get(_pair_payload_key(pair), data if len(normalized_pairs) == 1 else {})
        rate = _decimal_rate(payload.get('bid') or payload.get('ask') or payload.get('high'))
        if not rate:
            raise ValueError(f'A API de cotação não retornou um valor válido para {pair}.')
        source = payload.get('name') or f'AwesomeAPI {pair}'
        results[(currency_from, currency_to)] = (rate, source)
    return results


def fetch_usd_brl_rate():
    rates = fetch_exchange_rates([DEFAULT_EXCHANGE_PAIR])
    return rates[('USD', 'BRL')]


def save_exchange_rate(currency_from, currency_to, rate, source='manual'):
    currency_from = str(currency_from).strip().upper()
    currency_to = str(currency_to).strip().upper()
    rate = _decimal_rate(rate)
    if not rate:
        raise ValueError(f'Cotação {currency_from}/{currency_to} inválida.')

    ExchangeRate.objects.filter(currency_from=currency_from, currency_to=currency_to).update(is_active=False)
    obj = ExchangeRate.objects.create(
        currency_from=currency_from,
        currency_to=currency_to,
        rate=rate,
        source=source,
        is_active=True,
    )
    cache.set(_cache_key(currency_from, currency_to), obj.rate, settings.EXCHANGE_RATE_CACHE_SECONDS)
    return obj


def save_usd_brl_rate(rate, source='manual'):
    return save_exchange_rate('USD', 'BRL', rate, source=source)


def update_usd_brl_rate_from_api():
    rate, source = fetch_usd_brl_rate()
    return save_usd_brl_rate(rate, source=source)


def update_all_exchange_rates_from_api(pairs=None):
    rates = fetch_exchange_rates(pairs or settings.EXCHANGE_RATE_PAIRS)
    saved = []
    for (currency_from, currency_to), (rate, source) in rates.items():
        saved.append(save_exchange_rate(currency_from, currency_to, rate, source=source))
    return saved


def rate_updated_label(rate_obj):
    if not rate_obj:
        return ''
    local_time = timezone.localtime(rate_obj.updated_at)
    return local_time.strftime('%d/%m/%Y às %H:%M')
