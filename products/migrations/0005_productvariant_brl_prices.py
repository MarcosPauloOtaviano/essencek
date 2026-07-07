from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations, models


def money(value):
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def migrate_variant_prices_to_brl(apps, schema_editor):
    ProductVariant = apps.get_model('products', 'ProductVariant')
    ExchangeRate = apps.get_model('core', 'ExchangeRate')

    rate_obj = (
        ExchangeRate.objects
        .filter(currency_from='USD', currency_to='BRL', is_active=True)
        .order_by('-updated_at')
        .first()
    )
    rate = rate_obj.rate if rate_obj else Decimal('5.5000')

    for variant in ProductVariant.objects.all():
        update_fields = []
        if not variant.price and variant.price_usd:
            variant.price = money(variant.price_usd * rate)
            update_fields.append('price')
        if not variant.promotional_price and variant.promotional_price_usd:
            variant.promotional_price = money(variant.promotional_price_usd * rate)
            update_fields.append('promotional_price')
        if not variant.cost_price and variant.cost_price_usd:
            variant.cost_price = money(variant.cost_price_usd * rate)
            update_fields.append('cost_price')
        if update_fields:
            variant.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_exchangerate_alter_storesettings_store_name'),
        ('products', '0004_rename_category_to_decanter'),
    ]

    operations = [
        migrations.AddField(
            model_name='productvariant',
            name='price',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Preço de venda'),
        ),
        migrations.AddField(
            model_name='productvariant',
            name='promotional_price',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Preço promocional'),
        ),
        migrations.AddField(
            model_name='productvariant',
            name='cost_price',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Preço de custo (interno)'),
        ),
        migrations.AlterField(
            model_name='productvariant',
            name='price_usd',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Preço USD legado'),
        ),
        migrations.RunPython(migrate_variant_prices_to_brl, migrations.RunPython.noop),
    ]
