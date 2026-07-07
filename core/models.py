from decimal import Decimal

from django.db import models
from django.core.validators import RegexValidator

from core.utils import image_url_if_exists


class StoreSettings(models.Model):
    store_name = models.CharField('Nome da loja', max_length=100, default='Essence K Importados')
    logo = models.ImageField('Logo', upload_to='store/', blank=True, null=True)
    whatsapp = models.CharField('Telefone da loja', max_length=20, default='')
    instagram = models.CharField('Instagram', max_length=100, blank=True)
    email = models.EmailField('E-mail', blank=True)
    cep_origem = models.CharField('CEP de origem', max_length=9, blank=True)
    home_headline = models.CharField('Chamada principal da home', max_length=200,
                                     default='Produtos importados selecionados')
    home_subheadline = models.TextField('Subtexto da home', blank=True,
                                        default='Com pronta entrega e encomendas mensais.')
    about_text = models.TextField('Texto sobre a loja', blank=True)
    order_mode_active = models.BooleanField('Modo encomenda ativo', default=True)
    shipping_active = models.BooleanField('Frete ativo', default=True)
    payment_gateway = models.CharField('Gateway de pagamento', max_length=50,
                                       default='sandbox')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configurações da loja'
        verbose_name_plural = 'Configurações da loja'

    def __str__(self):
        return self.store_name

    @property
    def display_logo_url(self):
        return image_url_if_exists(self.logo)

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class NextTrip(models.Model):
    trip_date = models.DateField('Data da viagem')
    order_deadline = models.DateField('Data limite para encomendas')
    message = models.TextField('Mensagem personalizada', blank=True)
    is_active = models.BooleanField('Ativo', default=True)
    notes = models.TextField('Observações internas', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Próxima viagem'
        verbose_name_plural = 'Próximas viagens'
        ordering = ['-trip_date']

    def __str__(self):
        return f'Viagem em {self.trip_date.strftime("%d/%m/%Y")}'


class ExchangeRate(models.Model):
    currency_from = models.CharField('De', max_length=10, default='USD')
    currency_to = models.CharField('Para', max_length=10, default='BRL')
    rate = models.DecimalField('Cotação', max_digits=10, decimal_places=4)
    source = models.CharField('Fonte', max_length=100, blank=True)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)
    is_active = models.BooleanField('Ativa', default=True)

    class Meta:
        verbose_name = 'Cotação'
        verbose_name_plural = 'Cotações'
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.currency_from}/{self.currency_to} = {self.rate}'

    @classmethod
    def get_usd_brl(cls):
        from .services import get_usd_brl_rate
        return get_usd_brl_rate()
