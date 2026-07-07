from decimal import Decimal, ROUND_HALF_UP

from django.core.management.base import BaseCommand

from core.models import ExchangeRate
from products.models import Product


def to_usd(value, rate):
    if value is None:
        return None
    return (value / rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class Command(BaseCommand):
    help = 'Converte preços BRL legados para campos USD sem apagar os valores em BRL.'

    def add_arguments(self, parser):
        parser.add_argument('--rate', help='Cotação usada para conversão. Se omitida, usa a cotação ativa.')
        parser.add_argument('--overwrite', action='store_true', help='Recalcula mesmo quando o produto já possui USD.')

    def handle(self, *args, **options):
        rate = Decimal(str(options.get('rate') or ExchangeRate.get_usd_brl()))
        converted = 0
        for product in Product.objects.all():
            changed = False
            if options['overwrite'] or not product.price_usd:
                product.price_usd = to_usd(product.price, rate)
                changed = True
            if product.sale_price and (options['overwrite'] or not product.sale_price_usd):
                product.sale_price_usd = to_usd(product.sale_price, rate)
                changed = True
            if product.cost_price and (options['overwrite'] or not product.cost_price_usd):
                product.cost_price_usd = to_usd(product.cost_price, rate)
                changed = True
            if changed:
                product.save(update_fields=['price_usd', 'sale_price_usd', 'cost_price_usd', 'updated_at'])
                converted += 1
        self.stdout.write(self.style.SUCCESS(f'{converted} produto(s) convertidos usando 1 USD = R$ {rate}.'))
