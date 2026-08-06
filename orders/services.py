from urllib.parse import urlencode

from django.db.models import Sum
from django.db import transaction
from django.utils import timezone

from core.services import get_store_whatsapp_number
from products.models import Product, ProductVariant
from .models import Order


class InsufficientStockError(Exception):
    pass


def order_queryset_for_user(user):
    qs = Order.objects.all()
    if not user.is_staff:
        qs = qs.filter(customer=user)
    return qs


def build_order_whatsapp_url(order):
    number = get_store_whatsapp_number()
    if not number:
        return ''
    query = urlencode({'text': order.whatsapp_message})
    return f'https://wa.me/{number}?{query}'


def _status_for_stock(stock):
    if stock <= 0:
        return Product.STATUS_OUT_OF_STOCK
    if stock <= 3:
        return Product.STATUS_LOW_STOCK
    return Product.STATUS_AVAILABLE


def confirm_order_payment(order, confirmed_at=None):
    """Confirm payment and decrement stock exactly once."""
    confirmed_at = confirmed_at or timezone.now()
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.payment_status == 'confirmed':
            return False

        items = list(
            order.items.select_related('product', 'variant').filter(is_pre_order=False)
        )
        product_ids = {item.product_id for item in items if item.product_id}
        variant_ids = {item.variant_id for item in items if item.variant_id}
        products = {
            product.pk: product
            for product in Product.objects.select_for_update().filter(pk__in=product_ids)
        }
        variants = {
            variant.pk: variant
            for variant in ProductVariant.objects.select_for_update().filter(pk__in=variant_ids)
        }

        for item in items:
            product = products.get(item.product_id)
            variant = variants.get(item.variant_id) if item.variant_id else None
            if not product:
                raise InsufficientStockError(f'{item.product_name} não existe mais no catálogo.')
            if item.variant_id and not variant:
                raise InsufficientStockError(f'A variação de {item.product_name} não existe mais.')
            available = variant.stock if variant else product.stock
            if available < item.quantity:
                raise InsufficientStockError(
                    f'Estoque insuficiente para {item.product_name}. Disponível: {available}.'
                )

        order.payment_status = 'confirmed'
        order.status = Order.STATUS_PAYMENT_CONFIRMED
        order.payment_confirmed_at = confirmed_at
        order.save(update_fields=['payment_status', 'status', 'payment_confirmed_at', 'updated_at'])

        variant_product_ids = set()
        for item in items:
            product = products[item.product_id]
            variant = variants.get(item.variant_id) if item.variant_id else None
            if variant:
                variant.stock -= item.quantity
                variant.save(update_fields=['stock'])
                variant_product_ids.add(product.pk)
            else:
                product.stock -= item.quantity
                product.status = _status_for_stock(product.stock)
                product.save(update_fields=['stock', 'status', 'updated_at'])
            item.item_status = 'paid'
            item.save(update_fields=['item_status'])

        for product_id in variant_product_ids:
            product = products[product_id]
            total_stock = ProductVariant.objects.filter(
                product_id=product_id,
                is_active=True,
            ).aggregate(total=Sum('stock'))['total'] or 0
            product.stock = total_stock
            product.status = _status_for_stock(total_stock)
            product.save(update_fields=['stock', 'status', 'updated_at'])
        return True
