from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from .models import Order, OrderItem, PreOrderRequest
from .services import confirm_order_payment


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ['product_name', 'product_brand', 'unit_price', 'quantity', 'is_pre_order', 'item_status']
    readonly_fields = ['product_name', 'product_brand', 'unit_price', 'quantity', 'is_pre_order']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'customer_name', 'total', 'payment_method',
                    'payment_status', 'status', 'created_at']
    list_filter = ['status', 'payment_method', 'payment_status', 'created_at']
    search_fields = ['order_number', 'customer_name', 'customer_email', 'customer_whatsapp']
    readonly_fields = ['order_number', 'customer', 'created_at', 'updated_at']
    inlines = [OrderItemInline]
    actions = ['confirm_payment', 'mark_shipped', 'mark_completed', 'mark_cancelled']
    fieldsets = (
        ('Pedido', {
            'fields': ('order_number', 'customer', 'status', 'created_at')
        }),
        ('Cliente', {
            'fields': ('customer_name', 'customer_email', 'customer_whatsapp')
        }),
        ('Endereço de entrega', {
            'fields': ('address', 'address_number', 'address_complement',
                       'neighborhood', 'city', 'state', 'cep')
        }),
        ('Financeiro', {
            'fields': ('subtotal', 'shipping_cost', 'total',
                       'payment_method', 'payment_status', 'payment_link', 'gateway_payment_id')
        }),
        ('Rastreamento', {
            'fields': ('tracking_code', 'carrier', 'tracking_url', 'shipping_service')
        }),
        ('Observações', {
            'fields': ('customer_notes', 'internal_notes')
        }),
        ('Datas', {
            'fields': ('payment_confirmed_at', 'shipped_at', 'delivered_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.action(description='Confirmar pagamento')
    def confirm_payment(self, request, queryset):
        updated = 0
        for order in queryset:
            if confirm_order_payment(order):
                updated += 1
        self.message_user(request, f'{updated} pedido(s) confirmado(s).')

    @admin.action(description='Marcar como enviado')
    def mark_shipped(self, request, queryset):
        now = timezone.now()
        queryset.update(status=Order.STATUS_SHIPPED, shipped_at=now)
        self.message_user(request, 'Pedidos marcados como enviados.')

    @admin.action(description='Marcar como concluído')
    def mark_completed(self, request, queryset):
        now = timezone.now()
        queryset.update(status=Order.STATUS_COMPLETED, delivered_at=now)
        self.message_user(request, 'Pedidos concluídos.')

    @admin.action(description='Cancelar pedidos')
    def mark_cancelled(self, request, queryset):
        queryset.update(status=Order.STATUS_CANCELLED)
        self.message_user(request, 'Pedidos cancelados.')


@admin.register(PreOrderRequest)
class PreOrderRequestAdmin(admin.ModelAdmin):
    list_display = ['product_name', 'customer_name', 'whatsapp', 'status', 'agreed_price', 'created_at']
    list_filter = ['status', 'trip']
    search_fields = ['product_name', 'customer_name', 'whatsapp']
    list_editable = ['status']
