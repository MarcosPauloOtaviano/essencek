from django.db import migrations


def ensure_toplevel_categories(apps, schema_editor):
    Category = apps.get_model('products', 'Category')

    perfumes, _ = Category.objects.get_or_create(
        slug='perfumes',
        defaults={'name': 'Perfumes', 'order': 0},
    )
    perfumes.parent = None
    perfumes.save(update_fields=['parent'])

    fracionados, _ = Category.objects.get_or_create(
        slug='perfumes-fracionados',
        defaults={'name': 'Perfumes Fracionados', 'order': 1},
    )
    fracionados.parent = None
    fracionados.save(update_fields=['parent'])


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0002_brand_category_parent_product_cost_price_usd_and_more'),
    ]

    operations = [
        migrations.RunPython(ensure_toplevel_categories, migrations.RunPython.noop),
    ]
