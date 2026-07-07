from decimal import Decimal, InvalidOperation

from django import template


register = template.Library()


def _to_decimal(value):
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return None


@register.filter
def brl(value):
    value = _to_decimal(value)
    if value is None:
        return 'R$ 0,00'
    formatted = f'{value:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'R$ {formatted}'


@register.filter
def usd(value):
    value = _to_decimal(value)
    if value is None:
        return 'US$ 0.00'
    formatted = f'{value:,.2f}'
    return f'US$ {formatted}'


@register.filter
def rate_brl(value):
    value = _to_decimal(value)
    if value is None:
        return 'R$ 0,0000'
    formatted = f'{value:,.4f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'R$ {formatted}'
