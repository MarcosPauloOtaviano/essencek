"""
Shipping calculation via Frenet API.
Falls back to simulated table if Frenet is unavailable or unconfigured.
"""
import logging
import requests
from decimal import Decimal
from django.conf import settings

logger = logging.getLogger('shipping')

FRENET_URL = 'https://private-anon-65817d5e1c-frabornepr.apiary-proxy.com/shipping/quote'


def _get_package_from_cart(cart):
    total_weight_kg = Decimal('0')
    max_height = Decimal('0')
    max_width = Decimal('0')
    total_length = Decimal('0')

    items = cart.items.select_related('product')
    for item in items:
        p = item.product
        weight = p.weight if p.weight else Decimal('0.3')
        height = p.height if p.height else Decimal('10')
        width = p.width if p.width else Decimal('10')
        length = p.length if p.length else Decimal('15')

        total_weight_kg += weight * item.quantity
        max_height = max(max_height, height)
        max_width = max(max_width, width)
        total_length += length * item.quantity

    total_length = min(total_length, Decimal('100'))

    return {
        'weight': float(total_weight_kg),
        'height': float(max_height),
        'width': float(max_width),
        'length': float(total_length),
    }


def _call_frenet(cep_dest, package):
    token = getattr(settings, 'FRENET_TOKEN', '')
    sender_cep = getattr(settings, 'FRENET_SENDER_CEP', '85851130')

    if not token:
        return None

    payload = {
        'SellerCEP': sender_cep,
        'RecipientCEP': cep_dest,
        'ShipmentInvoiceValue': 100,
        'ShippingItemArray': [{
            'Height': package['height'],
            'Length': package['length'],
            'Width': package['width'],
            'Weight': package['weight'],
            'Quantity': 1,
        }],
        'RecipientCountry': 'BR',
    }

    try:
        resp = requests.post(
            'https://private-anon-65817d5e1c-frabornepr.apiary-proxy.com/shipping/quote',
            json=payload,
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'token': token,
            },
            timeout=10,
        )
        if resp.status_code != 200:
            logger.warning('Frenet returned status %s', resp.status_code)
            return None

        data = resp.json()
        services = data.get('ShippingSevicesArray') or data.get('ShippingServicesArray') or []

        options = []
        for svc in services:
            if svc.get('Error'):
                continue
            price = svc.get('ShippingPrice') or svc.get('OriginalShippingPrice')
            if not price or float(price) <= 0:
                continue
            options.append({
                'service': svc.get('ServiceCode', ''),
                'label': svc.get('ServiceDescription', svc.get('Carrier', 'Frete')),
                'price': float(price),
                'days': int(svc.get('DeliveryTime', 0)),
                'carrier': svc.get('Carrier', ''),
            })

        if options:
            options.sort(key=lambda x: x['price'])
            return options

        return None

    except requests.RequestException as exc:
        logger.warning('Frenet API error: %s', exc)
        return None


def get_cep_region(cep):
    prefix = int(cep[:2])
    if prefix in range(1, 20):
        return 'sp_capital'
    elif prefix in range(20, 30):
        return 'rj'
    elif prefix in range(30, 40):
        return 'mg'
    elif prefix in range(40, 50):
        return 'ba'
    elif prefix in range(50, 57):
        return 'pe'
    elif prefix in range(57, 60):
        return 'al'
    elif prefix in range(60, 64):
        return 'ce'
    elif prefix in range(64, 66):
        return 'pi'
    elif prefix in range(66, 69):
        return 'pa'
    elif prefix in range(69, 70):
        return 'am'
    elif prefix in range(70, 73):
        return 'df'
    elif prefix in range(73, 77):
        return 'go'
    elif prefix in range(77, 78):
        return 'to'
    elif prefix in range(78, 79):
        return 'mt'
    elif prefix in range(79, 80):
        return 'ms'
    elif prefix in range(80, 88):
        return 'pr'
    elif prefix in range(88, 90):
        return 'sc'
    elif prefix in range(90, 100):
        return 'rs'
    else:
        return 'other'


SHIPPING_TABLE = {
    'sp_capital': {'pac': (Decimal('15.90'), 5), 'sedex': (Decimal('28.90'), 2)},
    'rj':         {'pac': (Decimal('18.90'), 7), 'sedex': (Decimal('34.90'), 3)},
    'mg':         {'pac': (Decimal('17.90'), 6), 'sedex': (Decimal('32.90'), 3)},
    'ba':         {'pac': (Decimal('20.90'), 8), 'sedex': (Decimal('38.90'), 4)},
    'pr':         {'pac': (Decimal('17.90'), 7), 'sedex': (Decimal('32.90'), 3)},
    'sc':         {'pac': (Decimal('19.90'), 7), 'sedex': (Decimal('35.90'), 4)},
    'rs':         {'pac': (Decimal('19.90'), 8), 'sedex': (Decimal('35.90'), 4)},
    'df':         {'pac': (Decimal('20.90'), 7), 'sedex': (Decimal('36.90'), 3)},
    'other':      {'pac': (Decimal('24.90'), 10), 'sedex': (Decimal('42.90'), 5)},
}


def _fallback_shipping(cep):
    region = get_cep_region(cep)
    table = SHIPPING_TABLE.get(region, SHIPPING_TABLE['other'])
    options = []
    for service, (price, days) in table.items():
        label = 'PAC' if service == 'pac' else 'SEDEX'
        options.append({
            'service': service,
            'label': label,
            'price': float(price),
            'days': days,
            'carrier': 'Correios',
        })
    return options


def validate_cep(cep):
    """Validate CEP via ViaCEP. Returns True if valid."""
    try:
        resp = requests.get(f'https://viacep.com.br/ws/{cep}/json/', timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return not data.get('erro', False)
    except requests.RequestException:
        pass
    return False


def calculate_shipping(cep_dest, cart=None):
    cep_clean = cep_dest.replace('-', '').replace('.', '').strip()
    if len(cep_clean) != 8 or not cep_clean.isdigit():
        return {'error': 'CEP inválido.'}

    if not validate_cep(cep_clean):
        return {'error': 'CEP não encontrado. Verifique o número digitado.'}

    options = None
    if cart:
        package = _get_package_from_cart(cart)
        options = _call_frenet(cep_clean, package)

    if not options:
        options = _fallback_shipping(cep_clean)

    return {
        'success': True,
        'cep': cep_clean,
        'options': options,
    }
