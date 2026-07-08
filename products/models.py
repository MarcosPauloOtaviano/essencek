import os

from django.db import models
from django.utils.text import slugify
from django.urls import reverse
from django.templatetags.static import static

from core.models import ExchangeRate
from core.utils import image_url_if_exists, money
from .image_utils import build_web_product_image


DEFAULT_CATEGORY_IMAGE_MAP = {
    'perfumes': 'img/defaults/default-perfumes.jpg',
    'perfume': 'img/defaults/default-perfumes.jpg',
    'decanter': 'img/defaults/default-perfumes.jpg',
    'beleza-coreana': 'img/defaults/default-beleza-coreana.jpg',
    'beleza': 'img/defaults/default-beleza-coreana.jpg',
    'korean': 'img/defaults/default-beleza-coreana.jpg',
    'eletronicos': 'img/defaults/default-eletronicos.jpg',
    'eletronico': 'img/defaults/default-eletronicos.jpg',
    'eletrônicos': 'img/defaults/default-eletronicos.jpg',
}
DEFAULT_PRODUCT_IMAGE = 'img/defaults/default-default.jpg'


def normalize_gtin_value(value):
    normalized = ''.join(char for char in str(value or '') if char.isdigit())
    return normalized or None


def default_image_url_for_category(category):
    if not category:
        return static(DEFAULT_PRODUCT_IMAGE)
    key = (category.slug or category.name or '').casefold()
    for token, image_path in DEFAULT_CATEGORY_IMAGE_MAP.items():
        if token in key:
            return static(image_path)
    return static(DEFAULT_PRODUCT_IMAGE)


class Brand(models.Model):
    name = models.CharField('Nome', max_length=120)
    slug = models.SlugField('Slug', unique=True)
    description = models.TextField('Descrição', blank=True)
    logo = models.ImageField('Logo', upload_to='brands/', blank=True, null=True)
    is_active = models.BooleanField('Ativa', default=True)
    created_at = models.DateTimeField('Criado em', auto_now_add=True, null=True)

    class Meta:
        verbose_name = 'Marca'
        verbose_name_plural = 'Marcas'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Category(models.Model):
    name = models.CharField('Nome', max_length=100)
    slug = models.SlugField('Slug', unique=True)
    description = models.TextField('Descrição', blank=True)
    image = models.ImageField('Imagem', upload_to='categories/', blank=True, null=True)
    is_active = models.BooleanField('Ativa', default=True)
    order = models.PositiveIntegerField('Ordem', default=0)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', verbose_name='Categoria pai')

    class Meta:
        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorias'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('products:list') + f'?category={self.slug}'

    @property
    def is_subcategory(self):
        return self.parent is not None

    @property
    def display_image_url(self):
        return image_url_if_exists(self.image) or default_image_url_for_category(self)


class Product(models.Model):
    STATUS_AVAILABLE = 'available'
    STATUS_LOW_STOCK = 'low_stock'
    STATUS_PRE_ORDER = 'pre_order'
    STATUS_OUT_OF_STOCK = 'out_of_stock'
    STATUS_CHOICES = [
        (STATUS_AVAILABLE, 'Disponível'),
        (STATUS_LOW_STOCK, 'Últimas unidades'),
        (STATUS_PRE_ORDER, 'Sob encomenda'),
        (STATUS_OUT_OF_STOCK, 'Esgotado'),
    ]

    # Identity
    name = models.CharField('Nome', max_length=200)
    slug = models.SlugField('Slug', unique=True, blank=True)
    brand = models.CharField('Marca', max_length=100, blank=True)
    brand_fk = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name='products', verbose_name='Marca')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True,
                                  related_name='products', verbose_name='Categoria')
    short_description = models.CharField('Descrição curta', max_length=300, blank=True)
    description = models.TextField('Descrição completa', blank=True)

    # Pricing
    price = models.DecimalField('Preço de venda', max_digits=10, decimal_places=2)
    sale_price = models.DecimalField('Preço promocional', max_digits=10, decimal_places=2,
                                     null=True, blank=True)
    cost_price = models.DecimalField('Preço de custo (interno)', max_digits=10,
                                     decimal_places=2, null=True, blank=True)
    price_usd = models.DecimalField('Preço USD', max_digits=10, decimal_places=2, null=True, blank=True)
    sale_price_usd = models.DecimalField('Preço promo USD', max_digits=10, decimal_places=2, null=True, blank=True)
    cost_price_usd = models.DecimalField('Custo USD', max_digits=10, decimal_places=2, null=True, blank=True)
    gtin = models.CharField('GTIN/EAN', max_length=20, blank=True, null=True, unique=True)
    is_fractioned = models.BooleanField('Perfume fracionado', default=False)
    has_variants = models.BooleanField('Tem variações', default=False)

    # Stock
    stock = models.PositiveIntegerField('Estoque real', default=0)
    status = models.CharField('Status público', max_length=20, choices=STATUS_CHOICES,
                               default=STATUS_AVAILABLE)

    # Flags
    is_active = models.BooleanField('Ativo', default=True)
    is_featured = models.BooleanField('Destaque', default=False)
    is_on_sale = models.BooleanField('Promoção', default=False)
    is_pre_order = models.BooleanField('Sob encomenda', default=False)

    # Dimensions for shipping
    weight = models.DecimalField('Peso (kg)', max_digits=6, decimal_places=3, default=0)
    height = models.DecimalField('Altura (cm)', max_digits=6, decimal_places=1, default=0)
    width = models.DecimalField('Largura (cm)', max_digits=6, decimal_places=1, default=0)
    length = models.DecimalField('Comprimento (cm)', max_digits=6, decimal_places=1, default=0)

    # Internal
    internal_notes = models.TextField('Observações internas', blank=True)

    # Timestamps
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.gtin = normalize_gtin_value(self.gtin)
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            n = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base_slug}-{n}'
                n += 1
            self.slug = slug
        # Sync is_pre_order with status
        if self.status == self.STATUS_PRE_ORDER:
            self.is_pre_order = True
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('products:detail', kwargs={'slug': self.slug})

    @property
    def current_price(self):
        if self.is_on_sale and self.sale_price:
            return self.sale_price
        return self.price

    @property
    def display_price_usd(self):
        rate = ExchangeRate.get_usd_brl()
        if rate and self.price:
            return money(self.price / rate)
        if self.price_usd:
            return self.price_usd
        return None

    @property
    def display_sale_price_usd(self):
        if self.sale_price:
            from core.models import ExchangeRate
            rate = ExchangeRate.get_usd_brl()
            if rate:
                return money(self.sale_price / rate)
        if self.sale_price_usd:
            return self.sale_price_usd
        return None

    @property
    def price_brl(self):
        return self.price

    @property
    def sale_price_brl(self):
        if self.sale_price:
            return self.sale_price
        return None

    @property
    def current_price_usd(self):
        if self.is_on_sale and self.display_sale_price_usd:
            return self.display_sale_price_usd
        return self.display_price_usd

    @property
    def current_price_brl(self):
        if self.is_on_sale and self.sale_price:
            return self.sale_price
        return self.price

    @property
    def display_current_price_usd(self):
        return self.current_price_usd

    @property
    def display_current_price_brl(self):
        return self.current_price_brl

    @property
    def display_brand(self):
        if self.brand_fk:
            return self.brand_fk.name
        return self.brand

    @property
    def discount_percent(self):
        regular = self.price_brl
        sale = self.sale_price_brl
        if self.is_on_sale and regular and sale and regular > 0:
            return int(((regular - sale) / regular) * 100)
        return 0

    @property
    def discount_amount(self):
        regular = self.price_brl
        sale = self.sale_price_brl
        if self.is_on_sale and regular and sale and regular > sale:
            return regular - sale
        return 0

    @property
    def gross_profit(self):
        if self.cost_price:
            return self.current_price - self.cost_price
        return None

    @property
    def margin_percent(self):
        if self.cost_price and self.current_price > 0:
            return round(((self.current_price - self.cost_price) / self.current_price) * 100, 1)
        return None

    @property
    def main_image(self):
        img = self.images.filter(is_main=True).first()
        if not img:
            img = self.images.first()
        return img

    @property
    def default_image_url(self):
        return default_image_url_for_category(self.category)

    @property
    def display_image_url(self):
        img = self.main_image
        if img:
            return img.display_url
        return self.default_image_url

    def can_add_to_cart(self):
        return self.status != self.STATUS_OUT_OF_STOCK and self.is_active

    def get_status_display_class(self):
        return {
            self.STATUS_AVAILABLE: 'badge-available',
            self.STATUS_LOW_STOCK: 'badge-low-stock',
            self.STATUS_PRE_ORDER: 'badge-pre-order',
            self.STATUS_OUT_OF_STOCK: 'badge-out-of-stock',
        }.get(self.status, '')


def product_image_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    name = slugify(os.path.splitext(filename)[0]) or 'foto-produto'
    return f'products/{instance.product.slug}/{instance.product.pk}_{name}.{ext}'


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE,
                                related_name='images', verbose_name='Produto')
    image = models.ImageField('Imagem', upload_to=product_image_path)
    alt_text = models.CharField('Texto alternativo', max_length=200, blank=True)
    is_main = models.BooleanField('Foto principal', default=False)
    order = models.PositiveIntegerField('Ordem', default=0)

    class Meta:
        verbose_name = 'Imagem do produto'
        verbose_name_plural = 'Imagens do produto'
        ordering = ['-is_main', 'order']

    def __str__(self):
        return f'{self.product.name} - imagem {self.pk}'

    def save(self, *args, **kwargs):
        if self.image and not getattr(self.image, '_committed', True):
            self.image = build_web_product_image(self.image)
        # Ensure only one main image per product
        if self.is_main:
            ProductImage.objects.filter(product=self.product, is_main=True).exclude(
                pk=self.pk).update(is_main=False)
        super().save(*args, **kwargs)

    @property
    def file_exists(self):
        return bool(image_url_if_exists(self.image))

    @property
    def display_url(self):
        return image_url_if_exists(self.image) or self.product.default_image_url


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants', verbose_name='Produto')
    name = models.CharField('Nome da variação', max_length=120)
    volume_ml = models.PositiveIntegerField('Volume (ml)', null=True, blank=True)
    color = models.CharField('Cor', max_length=80, blank=True)
    size = models.CharField('Tamanho', max_length=80, blank=True)
    price = models.DecimalField('Preço de venda', max_digits=10, decimal_places=2, default=0)
    promotional_price = models.DecimalField('Preço promocional', max_digits=10, decimal_places=2, null=True, blank=True)
    cost_price = models.DecimalField('Preço de custo (interno)', max_digits=10, decimal_places=2, null=True, blank=True)
    price_usd = models.DecimalField('Preço USD legado', max_digits=10, decimal_places=2, null=True, blank=True)
    promotional_price_usd = models.DecimalField('Preço promo USD', max_digits=10, decimal_places=2, null=True, blank=True)
    cost_price_usd = models.DecimalField('Custo USD', max_digits=10, decimal_places=2, null=True, blank=True)
    stock = models.PositiveIntegerField('Estoque', default=0)
    sku = models.CharField('SKU', max_length=80, blank=True)
    gtin = models.CharField('GTIN/EAN', max_length=20, blank=True, null=True, unique=True)
    is_active = models.BooleanField('Ativo', default=True)
    order = models.PositiveIntegerField('Ordem', default=0)

    class Meta:
        verbose_name = 'Variação'
        verbose_name_plural = 'Variações'
        ordering = ['order', 'volume_ml', 'name']

    def __str__(self):
        return f'{self.product.name} - {self.name}'

    def save(self, *args, **kwargs):
        self.gtin = normalize_gtin_value(self.gtin)
        super().save(*args, **kwargs)

    @property
    def current_price(self):
        if self.promotional_price:
            return self.promotional_price
        if self.price:
            return self.price
        rate = ExchangeRate.get_usd_brl()
        if self.current_price_usd and rate:
            return money(self.current_price_usd * rate)
        return self.price

    @property
    def current_price_usd(self):
        rate = ExchangeRate.get_usd_brl()
        if self.promotional_price and rate:
            return money(self.promotional_price / rate)
        if self.price and rate:
            return money(self.price / rate)
        if self.promotional_price_usd:
            return self.promotional_price_usd
        return self.price_usd

    @property
    def price_brl(self):
        return self.current_price

    @property
    def status_display(self):
        if self.stock > 0:
            return 'Disponível'
        return 'Esgotado'
