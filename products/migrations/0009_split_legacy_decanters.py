import re

from django.db import migrations
from django.utils.text import slugify


def _category_for_volume(Category, volume):
    slug = f'Perfume-fracionado-decanter{volume}ml'
    category = Category.objects.filter(slug__iexact=slug).first()
    if category:
        return category
    return Category.objects.create(
        name=f'Decanter {volume}ml',
        slug=slug,
        is_active=True,
        order=45,
    )


def _unique_product_slug(Product, base, parent_id, volume):
    desired = slugify(f'{base}-decanter-{volume}ml')[:240]
    slug = desired
    counter = 2
    while Product.objects.filter(slug=slug).exclude(
        decanter_of_id=parent_id,
        decanter_volume_ml=volume,
    ).exists():
        suffix = f'-{counter}'
        slug = f'{desired[:255 - len(suffix)]}{suffix}'
        counter += 1
    return slug


def split_legacy_decanters(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    ProductVariant = apps.get_model('products', 'ProductVariant')
    ProductImage = apps.get_model('products', 'ProductImage')
    Category = apps.get_model('products', 'Category')
    HomeCollection = apps.get_model('products', 'HomeCollection')
    CartItem = apps.get_model('cart', 'CartItem')

    decanter_collection = HomeCollection.objects.filter(route_slug__iexact='decanter').first()

    parents = Product.objects.filter(is_fractioned=True, has_variants=True)
    for parent in parents:
        migrated = 0
        for variant in ProductVariant.objects.filter(product_id=parent.pk).order_by('order', 'volume_ml', 'pk'):
            match = re.search(r'(\d+)\s*ml', variant.name or '', flags=re.IGNORECASE)
            volume = variant.volume_ml or (int(match.group(1)) if match else None)
            if not volume:
                continue

            category = _category_for_volume(Category, volume)
            child = Product.objects.filter(
                decanter_of_id=parent.pk,
                decanter_volume_ml=volume,
            ).first()

            base_price = variant.price or parent.price
            promo_price = variant.promotional_price if (
                variant.promotional_price and variant.promotional_price < base_price
            ) else None
            child_status = parent.status
            if child_status != 'pre_order':
                child_status = 'available' if variant.stock > 0 else 'out_of_stock'

            values = {
                'name': f'{parent.name} — Decanter {volume} ml',
                'brand': parent.brand,
                'brand_fk_id': parent.brand_fk_id,
                'category_id': category.pk,
                'short_description': f'Decanter de {volume} ml de {parent.name}.',
                'description': parent.description,
                'price': base_price,
                'sale_price': promo_price,
                'cost_price': variant.cost_price,
                'stock': variant.stock,
                'status': child_status,
                'is_active': bool(parent.is_active and variant.is_active),
                'is_featured': False,
                'is_on_sale': bool(promo_price),
                'is_pre_order': parent.is_pre_order,
                'weight': parent.weight,
                'height': parent.height,
                'width': parent.width,
                'length': parent.length,
                'internal_notes': 'Criado automaticamente a partir de uma variação legada; edite a foto e o estoque no cadastro do decanter.',
                'product_kind': 'decanter',
                'decanter_of_id': parent.pk,
                'decanter_volume_ml': volume,
                'is_fractioned': False,
                'has_variants': False,
                'gtin': variant.gtin if variant.gtin and not Product.objects.filter(gtin=variant.gtin).exclude(pk=child.pk if child else None).exists() else None,
            }
            if child is None:
                values['slug'] = _unique_product_slug(Product, parent.slug, parent.pk, volume)
                child = Product.objects.create(**values)
            else:
                for key, value in values.items():
                    setattr(child, key, value)
                child.save(update_fields=list(values))

            if not ProductImage.objects.filter(product_id=child.pk).exists():
                for image in ProductImage.objects.filter(product_id=parent.pk).order_by('order', 'pk'):
                    ProductImage.objects.create(
                        product_id=child.pk,
                        image=image.image.name,
                        alt_text=f'{child.name} - {image.alt_text or parent.name}',
                        is_main=image.is_main,
                        order=image.order,
                    )

            # Keep visitors' existing carts intact while switching the line
            # from the legacy variation to the new standalone product.
            for item in CartItem.objects.filter(variant_id=variant.pk):
                duplicate = CartItem.objects.filter(
                    cart_id=item.cart_id, product_id=child.pk, variant__isnull=True,
                ).exclude(pk=item.pk).first()
                if duplicate:
                    duplicate.quantity += item.quantity
                    duplicate.save(update_fields=['quantity'])
                    item.delete()
                else:
                    item.product_id = child.pk
                    item.variant_id = None
                    item.save(update_fields=['product', 'variant'])

            variant.is_active = False
            variant.save(update_fields=['is_active'])
            migrated += 1

            if decanter_collection:
                child_collection, _ = HomeCollection.objects.get_or_create(
                    key=f'decanter-{volume}ml',
                    defaults={
                        'title': f'Decanter {volume} ml',
                        'route_slug': f'decanter-{volume}ml',
                        'description': f'Frascos de {volume} ml.',
                        'kind': 'category',
                        'parent_id': decanter_collection.pk,
                        'is_home_visible': False,
                        'is_active': True,
                        'order': 40 + volume,
                    },
                )
                child_collection.categories.add(category)

        if migrated:
            parent.is_fractioned = False
            parent.has_variants = False
            parent.save(update_fields=['is_fractioned', 'has_variants'])


class Migration(migrations.Migration):

    dependencies = [
        ('cart', '0002_alter_cartitem_unique_together_cartitem_variant_and_more'),
        ('products', '0008_product_catalog_type'),
    ]

    operations = [
        migrations.RunPython(split_legacy_decanters, migrations.RunPython.noop),
    ]
