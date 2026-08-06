import uuid
from decimal import Decimal

from django.db import models
from django.conf import settings
from django.templatetags.static import static
from django.utils import timezone

from core.utils import money
from products.models import Product


def generate_order_number():
    return 'ESK' + uuid.uuid4().hex[:8].upper()


def format_brl(value):
    value = money(Decimal(value or 0))
    return f'{value:,.2f}'.replace(',', '#').replace('.', ',').replace('#', '.')


class Order(models.Model):
    # General statuses
    STATUS_CREATED = 'created'
    STATUS_AWAITING_CONTACT = 'awaiting_contact'
    STATUS_AWAITING_PAYMENT = 'awaiting_payment'
    STATUS_PAYMENT_CONFIRMED = 'payment_confirmed'
    STATUS_PARTIAL_CONFIRMED = 'partial_confirmed'
    STATUS_SEPARATING = 'separating'
    STATUS_PARTIAL_SHIPPED = 'partial_shipped'
    STATUS_SHIPPED = 'shipped'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_CREATED, 'Pedido criado'),
        (STATUS_AWAITING_CONTACT, 'Aguardando confirmação no WhatsApp'),
        (STATUS_AWAITING_PAYMENT, 'Aguardando pagamento'),
        (STATUS_PAYMENT_CONFIRMED, 'Pagamento confirmado'),
        (STATUS_PARTIAL_CONFIRMED, 'Parcialmente confirmado'),
        (STATUS_SEPARATING, 'Em separação'),
        (STATUS_PARTIAL_SHIPPED, 'Parcialmente enviado'),
        (STATUS_SHIPPED, 'Enviado'),
        (STATUS_COMPLETED, 'Concluído'),
        (STATUS_CANCELLED, 'Cancelado'),
    ]

    PAYMENT_PIX = 'pix'
    PAYMENT_CREDIT_CARD = 'credit_card'
    PAYMENT_WHATSAPP = 'whatsapp'
    PAYMENT_CHOICES = [
        (PAYMENT_WHATSAPP, 'A combinar pelo WhatsApp'),
        (PAYMENT_PIX, 'Pix'),
        (PAYMENT_CREDIT_CARD, 'Cartão de crédito'),
    ]

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                  related_name='orders', verbose_name='Cliente')
    order_number = models.CharField('Número do pedido', max_length=20, unique=True,
                                     default=generate_order_number)

    # Customer info snapshot
    customer_name = models.CharField('Nome', max_length=200)
    customer_email = models.EmailField('E-mail')
    customer_whatsapp = models.CharField('Telefone', max_length=20)

    # Delivery address
    address = models.CharField('Endereço', max_length=255)
    address_number = models.CharField('Número', max_length=20)
    address_complement = models.CharField('Complemento', max_length=100, blank=True)
    neighborhood = models.CharField('Bairro', max_length=100, blank=True)
    city = models.CharField('Cidade', max_length=100)
    state = models.CharField('Estado', max_length=2)
    cep = models.CharField('CEP', max_length=9)

    # Financials
    subtotal = models.DecimalField('Subtotal', max_digits=10, decimal_places=2)
    shipping_cost = models.DecimalField('Frete', max_digits=8, decimal_places=2, default=0)
    total = models.DecimalField('Total', max_digits=10, decimal_places=2)
    subtotal_usd = models.DecimalField('Subtotal USD', max_digits=10, decimal_places=2, null=True, blank=True)
    total_usd = models.DecimalField('Total USD', max_digits=10, decimal_places=2, null=True, blank=True)
    exchange_rate = models.DecimalField('Cotação USD/BRL', max_digits=10, decimal_places=4, null=True, blank=True)

    # Payment
    payment_method = models.CharField('Forma de pagamento', max_length=20,
                                       choices=PAYMENT_CHOICES, default=PAYMENT_WHATSAPP)
    payment_status = models.CharField('Status do pagamento', max_length=50,
                                       default='pending')
    payment_link = models.URLField('Link de pagamento', blank=True)
    gateway_payment_id = models.CharField('ID pagamento gateway', max_length=100, blank=True)

    # Status and tracking
    status = models.CharField('Status', max_length=30, choices=STATUS_CHOICES,
                               default=STATUS_AWAITING_CONTACT)
    tracking_code = models.CharField('Código de rastreio', max_length=100, blank=True)
    carrier = models.CharField('Transportadora', max_length=100, blank=True)
    tracking_url = models.URLField('Link de rastreio', blank=True)
    shipping_service = models.CharField('Serviço de envio', max_length=100, blank=True)

    # Notes
    customer_notes = models.TextField('Observações do cliente', blank=True)
    internal_notes = models.TextField('Observações internas', blank=True)

    # Timestamps
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    payment_confirmed_at = models.DateTimeField('Pagamento confirmado em', null=True, blank=True)
    shipped_at = models.DateTimeField('Enviado em', null=True, blank=True)
    delivered_at = models.DateTimeField('Entregue em', null=True, blank=True)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Pedido'
        verbose_name_plural = 'Pedidos'
        ordering = ['-created_at']

    def __str__(self):
        return f'Pedido {self.order_number}'

    @property
    def whatsapp_message(self):
        items = list(self.items.all())
        item_lines = []
        for index, item in enumerate(items, start=1):
            variant = f' - {item.display_variant_label}' if item.display_variant_label else ''
            item_lines.append(
                f'{index}. {item.quantity}x {item.product_name}{variant}\n'
                f'   R$ {format_brl(item.unit_price)} cada | Subtotal R$ {format_brl(item.subtotal)}'
            )

        delivery = self.shipping_service or 'Entrega a confirmar'
        address = ''
        if self.shipping_service != 'Retirada na loja' and self.address:
            address = (
                f'\n*Endereço:* {self.address}, {self.address_number}'
                f'{f" - {self.address_complement}" if self.address_complement else ""}'
                f'\n{self.neighborhood + " - " if self.neighborhood else ""}'
                f'{self.city}/{self.state} - CEP {self.cep}'
            )
        notes = f'\n*Observações:* {self.customer_notes[:300]}' if self.customer_notes else ''
        created_at = timezone.localtime(self.created_at).strftime('%d/%m/%Y às %H:%M')
        message = (
            'Olá! Quero finalizar este pedido da EssenceK:\n\n'
            f'*Pedido:* #{self.order_number}\n'
            f'*Data:* {created_at}\n\n'
            f'*Produtos:*\n' + '\n'.join(item_lines) + '\n\n'
            f'*Subtotal:* R$ {format_brl(self.subtotal)}\n'
            f'*Frete:* R$ {format_brl(self.shipping_cost)}\n'
            f'*Total:* R$ {format_brl(self.total)}\n\n'
            f'*Nome:* {self.customer_name}\n'
            f'*Forma de entrega:* {delivery}'
            f'{address}{notes}\n\n'
            'Este pedido aguarda confirmação de disponibilidade, entrega e pagamento.'
        )

        if len(message) <= 3500:
            return message

        compact_items = item_lines[:12]
        remaining = len(item_lines) - len(compact_items)
        if remaining > 0:
            compact_items.append(f'... e mais {remaining} item(ns) no pedido.')
        order_url = f'{settings.SITE_URL.rstrip("/")}/conta/meus-pedidos/{self.order_number}/'
        return (
            'Olá! Quero finalizar este pedido da EssenceK:\n\n'
            f'*Pedido:* #{self.order_number}\n'
            f'*Produtos:*\n' + '\n'.join(compact_items) + '\n\n'
            f'*Total:* R$ {format_brl(self.total)}\n'
            f'*Forma de entrega:* {delivery}\n'
            f'*Detalhes do pedido:* {order_url}\n\n'
            'Este pedido aguarda confirmação de disponibilidade, entrega e pagamento.'
        )

    RETRYABLE_STATUSES = {STATUS_CREATED, STATUS_AWAITING_PAYMENT}

    @property
    def can_retry_payment(self):
        return (
            self.payment_method != self.PAYMENT_WHATSAPP
            and
            self.status in self.RETRYABLE_STATUSES
            and self.payment_status in ('pending', '')
        )

    @property
    def active_payment(self):
        return self.payments.filter(is_active=True).order_by('-created_at').first()

    @property
    def display_subtotal_usd(self):
        if self.subtotal_usd:
            return self.subtotal_usd
        if self.exchange_rate:
            return money(self.subtotal / self.exchange_rate)
        return None

    @property
    def display_total_usd(self):
        if self.total_usd:
            return self.total_usd
        if self.exchange_rate:
            return money(self.total / self.exchange_rate)
        return self.display_subtotal_usd


class OrderItem(models.Model):
    ITEM_STATUS_CHOICES = [
        ('ready', 'Pronta entrega'),
        ('pre_order', 'Sob encomenda'),
        ('awaiting', 'Aguardando confirmação'),
        ('confirmed', 'Confirmado'),
        ('paid', 'Pago'),
        ('separating', 'Em separação'),
        ('shipped', 'Enviado'),
        ('delivered', 'Entregue'),
        ('cancelled', 'Cancelado'),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    variant = models.ForeignKey('products.ProductVariant', on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items', verbose_name='Variação')
    product_name = models.CharField('Nome do produto', max_length=200)
    product_brand = models.CharField('Marca', max_length=100, blank=True)
    unit_price = models.DecimalField('Preço unitário', max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField('Quantidade')
    variant_name = models.CharField('Variação', max_length=120, blank=True)
    variant_volume_ml = models.PositiveIntegerField('Volume ml', null=True, blank=True)
    unit_price_usd = models.DecimalField('Preço unit. USD', max_digits=10, decimal_places=2, null=True, blank=True)
    product_category = models.CharField('Categoria', max_length=100, blank=True)
    is_pre_order = models.BooleanField('Sob encomenda', default=False)
    item_status = models.CharField('Status do item', max_length=20,
                                    choices=ITEM_STATUS_CHOICES, default='ready')

    class Meta:
        verbose_name = 'Item do pedido'
        verbose_name_plural = 'Itens do pedido'

    def __str__(self):
        return f'{self.quantity}x {self.product_name}'

    @property
    def subtotal(self):
        return self.unit_price * self.quantity

    @property
    def display_unit_price_usd(self):
        if self.unit_price_usd:
            return self.unit_price_usd
        if self.order.exchange_rate:
            return money(self.unit_price / self.order.exchange_rate)
        return None

    @property
    def display_subtotal_usd(self):
        if not self.display_unit_price_usd:
            return None
        return self.display_unit_price_usd * self.quantity

    @property
    def display_image_url(self):
        if self.product:
            return self.product.display_image_url
        return static('img/defaults/default-default.jpg')

    @property
    def display_variant_label(self):
        if self.variant_name:
            return self.variant_name
        if self.variant_volume_ml:
            return f'{self.variant_volume_ml}ml'
        if self.variant:
            return self.variant.name
        return ''


class PreOrderRequest(models.Model):
    STATUS_CHOICES = [
        ('received', 'Solicitação recebida'),
        ('awaiting_admin', 'Aguardando confirmação da admin'),
        ('confirmed', 'Produto confirmado'),
        ('awaiting_payment', 'Aguardando pagamento'),
        ('paid', 'Pago'),
        ('awaiting_arrival', 'Aguardando chegada'),
        ('ready_to_ship', 'Disponível para envio'),
        ('shipped', 'Enviado'),
        ('delivered', 'Entregue'),
        ('cancelled', 'Cancelado'),
    ]

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name='pre_orders', null=True, blank=True)
    customer_name = models.CharField('Nome', max_length=200)
    whatsapp = models.CharField('Telefone', max_length=20)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField('Nome do produto', max_length=200)
    status = models.CharField('Status', max_length=30, choices=STATUS_CHOICES, default='received')
    agreed_price = models.DecimalField('Valor combinado', max_digits=10, decimal_places=2,
                                        null=True, blank=True)
    payment_link = models.URLField('Link de pagamento', blank=True)
    notes = models.TextField('Observações', blank=True)
    trip = models.ForeignKey('core.NextTrip', on_delete=models.SET_NULL, null=True, blank=True,
                              verbose_name='Viagem')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Encomenda'
        verbose_name_plural = 'Encomendas'
        ordering = ['-created_at']

    def __str__(self):
        return f'Encomenda {self.product_name} — {self.customer_name}'
