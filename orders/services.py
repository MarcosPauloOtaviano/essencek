from django.db import transaction
from django.utils import timezone

from .models import Order


def order_queryset_for_user(user):
    qs = Order.objects.all()
    if not user.is_staff:
        qs = qs.filter(customer=user)
    return qs


def confirm_order_payment(order, confirmed_at=None):
    """Confirm payment and decrement stock exactly once."""
    confirmed_at = confirmed_at or timezone.now()
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.payment_status == 'confirmed':
            return False

        order.payment_status = 'confirmed'
        order.status = Order.STATUS_PAYMENT_CONFIRMED
        order.payment_confirmed_at = confirmed_at
        order.save(update_fields=['payment_status', 'status', 'payment_confirmed_at', 'updated_at'])

        for item in order.items.select_related('product', 'variant').filter(is_pre_order=False):
            if item.variant:
                item.variant.stock = max(0, item.variant.stock - item.quantity)
                item.variant.save(update_fields=['stock'])
            elif item.product:
                item.product.stock = max(0, item.product.stock - item.quantity)
                item.product.save(update_fields=['stock'])
            item.item_status = 'paid'
            item.save(update_fields=['item_status'])
        return True
