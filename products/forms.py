from django import forms
from core.utils import sanitize_text
from .models import Product, Category, ProductImage, Brand, ProductVariant, normalize_gtin_value
from .image_utils import (
    ALLOWED_IMAGE_EXTENSIONS,
    MAX_IMAGE_UPLOAD_SIZE,
    validate_product_image_upload,
)


MAX_PRODUCT_IMAGES_PER_UPLOAD = 12
VALID_GTIN_LENGTHS = {8, 12, 13, 14}


def clean_gtin_field(value):
    gtin = normalize_gtin_value(value)
    if gtin and len(gtin) not in VALID_GTIN_LENGTHS:
        raise forms.ValidationError('Informe um GTIN/EAN válido com 8, 12, 13 ou 14 dígitos.')
    return gtin


class MultiFileInput(forms.FileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.FileField):
    widget = MultiFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        files = data if isinstance(data, (list, tuple)) else [data]
        if len(files) > MAX_PRODUCT_IMAGES_PER_UPLOAD:
            raise forms.ValidationError(f'Envie no máximo {MAX_PRODUCT_IMAGES_PER_UPLOAD} fotos por vez.')
        for image in files:
            validate_product_image_upload(image)
        return files


class ProductForm(forms.ModelForm):
    images = MultipleImageField(
        label='Adicionar fotos',
        widget=MultiFileInput(attrs={
            'multiple': True,
            'accept': 'image/*,.heic,.heif',
            'id': 'imageInput',
            'class': 'upload-input',
        }),
        required=False
    )

    class Meta:
        model = Product
        fields = [
            'name', 'brand_fk', 'category', 'short_description', 'description',
            'price', 'sale_price', 'cost_price',
            'price_usd', 'sale_price_usd', 'cost_price_usd',
            'stock', 'status', 'is_active', 'is_featured', 'is_on_sale', 'is_pre_order',
            'is_fractioned', 'has_variants', 'gtin',
            'weight', 'height', 'width', 'length',
            'internal_notes',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
            'short_description': forms.TextInput(attrs={'placeholder': 'Breve descrição para o card'}),
            'internal_notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['price'].required = True
        self.fields['sale_price'].required = False
        self.fields['cost_price'].required = False
        self.fields['price_usd'].required = False
        self.fields['sale_price_usd'].required = False
        self.fields['cost_price_usd'].required = False
        self.fields['price'].label = 'Preço de venda em reais'
        self.fields['sale_price'].label = 'Preço promocional em reais'
        self.fields['cost_price'].label = 'Preço de custo em reais'
        self.fields['price_usd'].label = 'Preço USD legado'
        self.fields['sale_price_usd'].label = 'Preço promocional USD legado'
        self.fields['cost_price_usd'].label = 'Custo USD legado'

    def clean(self):
        cleaned = super().clean()
        price = cleaned.get('price')
        sale_price = cleaned.get('sale_price')
        stock = cleaned.get('stock')
        status = cleaned.get('status')
        is_on_sale = cleaned.get('is_on_sale')
        is_pre_order = cleaned.get('is_pre_order') or status == Product.STATUS_PRE_ORDER

        if price is None or price <= 0:
            self.add_error('price', 'Informe o preço de venda em reais maior que zero.')
        for field_name in (
            'sale_price', 'cost_price',
            'price_usd', 'sale_price_usd', 'cost_price_usd',
            'weight', 'height', 'width', 'length',
        ):
            value = cleaned.get(field_name)
            if value is not None and value < 0:
                self.add_error(field_name, 'Informe um valor igual ou maior que zero.')
        if is_on_sale and not sale_price:
            self.add_error('sale_price', 'Informe o preço promocional em reais.')
        if price and sale_price and sale_price >= price:
            self.add_error('sale_price', 'O preço promocional deve ser menor que o preço de venda.')
        if not is_pre_order and status != Product.STATUS_OUT_OF_STOCK and stock is not None and stock <= 0:
            self.add_error('stock', 'Produtos de pronta entrega precisam ter estoque ou status esgotado.')
        return cleaned

    def clean_name(self):
        return sanitize_text(self.cleaned_data.get('name') or '')

    def clean_short_description(self):
        return sanitize_text(self.cleaned_data.get('short_description') or '')

    def clean_description(self):
        return sanitize_text(self.cleaned_data.get('description') or '')

    def clean_internal_notes(self):
        return sanitize_text(self.cleaned_data.get('internal_notes') or '')

    def clean_gtin(self):
        return clean_gtin_field(self.cleaned_data.get('gtin'))

    def save(self, commit=True):
        product = super().save(commit=False)
        if product.brand_fk:
            product.brand = product.brand_fk.name
        if commit:
            product.save()
            self.save_m2m()
        return product


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'slug', 'parent', 'description', 'image', 'is_active', 'order']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            validate_product_image_upload(image)
        return image


class BrandForm(forms.ModelForm):
    class Meta:
        model = Brand
        fields = ['name', 'slug', 'description', 'logo', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = [
            'name', 'volume_ml', 'color', 'size',
            'price', 'promotional_price', 'cost_price',
            'price_usd', 'promotional_price_usd', 'cost_price_usd',
            'stock', 'sku', 'gtin', 'is_active', 'order',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['price'].required = True
        for field_name in ('price_usd', 'promotional_price_usd', 'cost_price_usd'):
            self.fields[field_name].required = False

    def clean(self):
        cleaned = super().clean()
        price = cleaned.get('price')
        promotional_price = cleaned.get('promotional_price')
        if price is None or price <= 0:
            self.add_error('price', 'Informe o preço em reais maior que zero.')
        if promotional_price and price and promotional_price >= price:
            self.add_error('promotional_price', 'O preço promocional deve ser menor que o preço de venda.')
        for field_name in (
            'promotional_price', 'cost_price',
            'price_usd', 'promotional_price_usd', 'cost_price_usd',
        ):
            value = cleaned.get(field_name)
            if value is not None and value < 0:
                self.add_error(field_name, 'Informe um valor igual ou maior que zero.')
        return cleaned

    def clean_gtin(self):
        return clean_gtin_field(self.cleaned_data.get('gtin'))


ProductVariantFormSet = forms.inlineformset_factory(
    Product, ProductVariant,
    form=ProductVariantForm,
    extra=1, can_delete=True,
)


ProductImageFormSet = forms.inlineformset_factory(
    Product, ProductImage,
    fields=['image', 'alt_text', 'is_main', 'order'],
    extra=3, can_delete=True
)
