from django.contrib import admin
from .models import ShippingRate


@admin.register(ShippingRate)
class ShippingRateAdmin(admin.ModelAdmin):
    list_display = ['name', 'carrier', 'service', 'price', 'min_days', 'max_days', 'is_active']
    list_editable = ['price', 'is_active']
