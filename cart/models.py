from django.db import models
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

    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def subtotal(self):
        return sum(item.subtotal for item in self.items.all())

    @property
    def subtotal_usd(self):
        values = [item.subtotal_usd for item in self.items.all()]
        if any(value is None for value in values):
            return None
        return sum(values)

    @property
    def has_pre_order(self):
        return self.items.filter(product__is_pre_order=True).exists()

    @property
    def has_in_stock(self):
        return self.items.filter(product__is_pre_order=False).exists()


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
