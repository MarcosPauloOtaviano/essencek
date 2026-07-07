from django.db import models
from orders.models import Order


class Payment(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CANCELLED = 'cancelled'
    STATUS_REFUNDED = 'refunded'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pendente'),
        (STATUS_APPROVED, 'Aprovado'),
        (STATUS_REJECTED, 'Rejeitado'),
        (STATUS_CANCELLED, 'Cancelado'),
        (STATUS_REFUNDED, 'Estornado'),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE,
                               related_name='payments', verbose_name='Pedido')
    gateway = models.CharField('Gateway', max_length=50, default='sandbox')
    gateway_id = models.CharField('ID no gateway', max_length=200, blank=True)
    gateway_status = models.CharField('Status no gateway', max_length=50, blank=True)
    status = models.CharField('Status', max_length=20, choices=STATUS_CHOICES,
                               default=STATUS_PENDING)
    amount = models.DecimalField('Valor', max_digits=10, decimal_places=2)
    payment_method = models.CharField('Método', max_length=20, blank=True)
    payment_link = models.URLField('Link de pagamento', blank=True)
    pix_code = models.TextField('Código PIX copia-e-cola', blank=True)
    pix_qr_code = models.TextField('QR Code PIX (base64)', blank=True)
    raw_response = models.JSONField('Resposta do gateway', default=dict, blank=True)
    is_active = models.BooleanField('Tentativa ativa', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pagamento'
        verbose_name_plural = 'Pagamentos'

    def __str__(self):
        return f'Pagamento {self.order.order_number} — {self.get_status_display()}'
