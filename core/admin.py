from django.contrib import admin
from django.contrib import messages
from .models import StoreSettings, NextTrip, ExchangeRate, ShowcaseSlide
from .services import update_usd_brl_rate_from_api


@admin.register(StoreSettings)
class StoreSettingsAdmin(admin.ModelAdmin):
    list_display = ['store_name', 'whatsapp', 'email', 'updated_at']


@admin.register(NextTrip)
class NextTripAdmin(admin.ModelAdmin):
    list_display = ['trip_date', 'order_deadline', 'is_active', 'created_at']
    list_editable = ['is_active']


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ['currency_from', 'currency_to', 'rate', 'source', 'is_active', 'updated_at']
    list_filter = ['currency_from', 'currency_to', 'is_active']
    readonly_fields = ['updated_at']
    actions = ['mark_active', 'update_from_api']

    @admin.action(description='Marcar cotação selecionada como ativa')
    def mark_active(self, request, queryset):
        selected = queryset.first()
        if not selected:
            return
        ExchangeRate.objects.filter(currency_from=selected.currency_from, currency_to=selected.currency_to).update(is_active=False)
        selected.is_active = True
        selected.save(update_fields=['is_active'])
        self.message_user(request, 'Cotação ativa atualizada.')

    @admin.action(description='Buscar cotação USD/BRL da API')
    def update_from_api(self, request, queryset):
        try:
            rate = update_usd_brl_rate_from_api()
        except Exception as exc:
            self.message_user(request, f'Não foi possível atualizar a cotação: {exc}', level=messages.ERROR)
        else:
            self.message_user(request, f'Cotação atualizada: 1 USD = R$ {rate.rate}.')


@admin.register(ShowcaseSlide)
class ShowcaseSlideAdmin(admin.ModelAdmin):
    list_display = ['title', 'position', 'is_active', 'updated_at']
    list_filter = ['is_active']
    list_editable = ['position', 'is_active']
