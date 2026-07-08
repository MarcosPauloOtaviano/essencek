from django.contrib import admin
from django import forms
from django.utils.html import format_html
from .forms import ProductForm
from .models import Brand, Category, Product, ProductImage, ProductVariant
from .image_utils import validate_product_image_upload


class ProductImageInlineForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = ['image', 'alt_text', 'is_main', 'order']

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            validate_product_image_upload(image)
        return image


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'order']
    list_editable = ['is_active', 'order']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active']
    list_editable = ['is_active']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    form = ProductImageInlineForm
    extra = 3
    fields = ['image', 'alt_text', 'is_main', 'order']


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ['name', 'volume_ml', 'price', 'promotional_price', 'cost_price', 'stock', 'sku', 'gtin', 'is_active', 'order']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_brand', 'category', 'price', 'sale_price',
                    'stock', 'status', 'gtin', 'is_active', 'is_featured', 'is_on_sale']
    list_editable = ['is_active', 'is_featured', 'is_on_sale', 'status', 'stock']
    list_filter = ['category', 'brand_fk', 'status', 'is_active', 'is_featured', 'is_on_sale', 'is_pre_order', 'is_fractioned']
    search_fields = ['name', 'brand', 'brand_fk__name', 'description', 'gtin', 'variants__gtin']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline, ProductVariantInline]
    fieldsets = (
        ('Informações básicas', {
            'fields': ('name', 'slug', 'brand_fk', 'category', 'short_description', 'description')
        }),
        ('Preços em reais', {
            'fields': ('price', 'sale_price', 'cost_price')
        }),
        ('Valores em dólar legados/referência', {
            'fields': ('price_usd', 'sale_price_usd', 'cost_price_usd'),
            'classes': ('collapse',),
        }),
        ('Estoque e status', {
            'fields': ('stock', 'status', 'is_active', 'is_featured', 'is_on_sale', 'is_pre_order', 'is_fractioned', 'has_variants', 'gtin')
        }),
        ('Dimensões para frete', {
            'fields': ('weight', 'height', 'width', 'length'),
            'classes': ('collapse',),
        }),
        ('Uso interno', {
            'fields': ('internal_notes',),
            'classes': ('collapse',),
        }),
    )


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ['product', 'name', 'volume_ml', 'price', 'stock', 'gtin', 'is_active']
    list_filter = ['is_active', 'product__category']
    search_fields = ['product__name', 'name', 'sku', 'gtin']
