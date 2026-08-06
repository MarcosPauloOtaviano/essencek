from django.db import models
from django.db.models import Sum
from django.conf import settings
from products.models import Product


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                null=True, blank=True, related_name='cart')
    session_key = models.CharField(max_length=40, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Carrinho'
        verbose_name_plural = 'Carrinhos'

    def __str__(self):
        return f'Carrinho de {self.user or self.session_key}'

    def _loaded_items(self):
        return getattr(self, '_prefetched_objects_cache', {}).get('items')

    @property
    def total_items(self):
        items = self._loaded_items()
        if items is not None:
            return sum(item.quantity for item in items)
        return self.items.aggregate(total=Sum('quantity'))['total'] or 0

    @property
    def subtotal(self):
        items = self._loaded_items()
        return sum(item.subtotal for item in (items if items is not None else self.items.all()))

    @property
    def subtotal_usd(self):
        items = self._loaded_items()
        values = [item.subtotal_usd for item in (items if items is not None else self.items.all())]
        if any(value is None for value in values):
            return None
        return sum(values)

    @property
    def has_pre_order(self):
        items = self._loaded_items()
        if items is not None:
            return any(item.product.is_pre_order for item in items)
        return self.items.filter(product__is_pre_order=True).exists()

    @property
    def has_in_stock(self):
        items = self._loaded_items()
        if items is not None:
            return any(not item.product.is_pre_order for item in items)
        return self.items.filter(product__is_pre_order=False).exists()

    @property
    def has_unavailable_items(self):
        items = self._loaded_items()
        return any(
            not item.is_available
            for item in (items if items is not None else self.items.select_related('product', 'variant'))
        )


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey('products.ProductVariant', on_delete=models.CASCADE, null=True, blank=True, verbose_name='Variação')
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = 'Item do carrinho'
        unique_together = ['cart', 'product', 'variant']

    def __str__(self):
        return f'{self.quantity}x {self.product.name}'

    @property
    def unit_price(self):
        if self.variant:
            return self.variant.current_price
        return self.product.current_price

    @property
    def unit_price_usd(self):
        if self.variant:
            return self.variant.current_price_usd
        return self.product.display_current_price_usd

    @property
    def subtotal(self):
        return self.unit_price * self.quantity

    @property
    def subtotal_usd(self):
        if not self.unit_price_usd:
            return None
        return self.unit_price_usd * self.quantity

    @property
    def is_available(self):
        if not self.product.can_add_to_cart():
            return False
        if self.product.is_fractioned and self.product.has_variants:
            if not self.variant or not self.variant.is_active:
                return False
            return self.product.is_pre_order or self.quantity <= self.variant.stock
        return self.product.is_pre_order or self.quantity <= self.product.stock
