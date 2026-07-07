from django.db import migrations


def rename_to_decanter(apps, schema_editor):
    Category = apps.get_model('products', 'Category')
    try:
        cat = Category.objects.get(slug='perfumes-fracionados')
        cat.name = 'Decanter'
        cat.slug = 'decanter'
        cat.parent = None
        cat.save(update_fields=['name', 'slug', 'parent'])
    except Category.DoesNotExist:
        Category.objects.get_or_create(
            slug='decanter',
            defaults={'name': 'Decanter', 'order': 1, 'parent': None},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0003_ensure_toplevel_perfume_categories'),
    ]

    operations = [
        migrations.RunPython(rename_to_decanter, migrations.RunPython.noop),
    ]
