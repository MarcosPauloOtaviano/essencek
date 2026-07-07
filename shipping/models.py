from django.db import models


class ShippingRate(models.Model):
    """Manual shipping rate override (for specific regions or flat rates)."""
    name = models.CharField('Nome', max_length=100)
    carrier = models.CharField('Transportadora', max_length=100, default='Correios')
    service = models.CharField('Serviço', max_length=50)
    price = models.DecimalField('Preço', max_digits=8, decimal_places=2)
    min_days = models.PositiveIntegerField('Prazo mínimo (dias)', default=1)
    max_days = models.PositiveIntegerField('Prazo máximo (dias)', default=10)
    is_active = models.BooleanField('Ativo', default=True)

    class Meta:
        verbose_name = 'Tabela de frete'
        verbose_name_plural = 'Tabela de fretes'

    def __str__(self):
        return f'{self.name} — R$ {self.price}'
