from pathlib import PurePosixPath

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import migrations


def copy_decanter_images(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    ProductImage = apps.get_model('products', 'ProductImage')

    for product in Product.objects.filter(product_kind='decanter'):
        own_prefix = f'products/{product.slug}/{product.pk}_'
        for image in ProductImage.objects.filter(product_id=product.pk).order_by('pk'):
            source_name = image.image.name
            if not source_name or source_name.startswith(own_prefix):
                continue

            with default_storage.open(source_name, 'rb') as source:
                content = source.read()
            suffix = PurePosixPath(source_name).suffix or '.jpg'
            target_name = f'{own_prefix}decanter-{image.pk}{suffix}'
            saved_name = default_storage.save(target_name, ContentFile(content, name=target_name))
            image.image.name = saved_name
            image.save(update_fields=['image'])


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0009_split_legacy_decanters'),
    ]

    operations = [
        migrations.RunPython(copy_decanter_images, migrations.RunPython.noop),
    ]
