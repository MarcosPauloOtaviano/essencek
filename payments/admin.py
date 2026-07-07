from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['order', 'gateway', 'amount', 'status', 'payment_method', 'is_active', 'created_at']
    list_filter = ['status', 'gateway', 'payment_method', 'is_active']
    search_fields = ['order__order_number', 'gateway_id']
    readonly_fields = ['order', 'gateway_id', 'raw_response', 'pix_qr_code', 'created_at']
    actions = ['approve_payment']

    @admin.action(description='Aprovar pagamento manualmente')
    def approve_payment(self, request, queryset):
        from orders.services import confirm_order_payment
        for payment in queryset:
            payment.status = Payment.STATUS_APPROVED
            payment.gateway_status = 'manual_approval'
            payment.save()
            Payment.objects.filter(order=payment.order, is_active=True).exclude(
                pk=payment.pk,
            ).update(is_active=False, status=Payment.STATUS_CANCELLED)
            confirm_order_payment(payment.order)
        self.message_user(request, f'{queryset.count()} pagamento(s) aprovado(s).')
