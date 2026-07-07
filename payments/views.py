from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings as django_settings

from orders.models import Order
from orders.services import order_queryset_for_user
from .services import PaymentService


MAX_WEBHOOK_BYTES = 64 * 1024


@login_required
def payment_pix(request, order_number):
    order = get_object_or_404(order_queryset_for_user(request.user), order_number=order_number)
    service = PaymentService()
    payment = service.create_payment(order)
    return render(request, 'checkout/pix.html', {
        'order': order,
        'payment': payment,
        'payment_is_simulated': getattr(django_settings, 'PAYMENT_SANDBOX', True),
    })


@login_required
def payment_link(request, order_number):
    order = get_object_or_404(order_queryset_for_user(request.user), order_number=order_number)
    service = PaymentService()
    payment = service.create_payment(order)
    return render(request, 'checkout/payment_link.html', {
        'order': order,
        'payment': payment,
        'payment_is_simulated': getattr(django_settings, 'PAYMENT_SANDBOX', True),
    })


@login_required
def retry_payment(request, order_number):
    order = get_object_or_404(
        Order.objects.filter(customer=request.user),
        order_number=order_number,
    )
    if not order.can_retry_payment:
        messages.error(request, 'Este pedido não permite nova tentativa de pagamento.')
        return redirect('order_detail', order_number=order.order_number)

    service = PaymentService()
    payment = service.create_payment(order)

    if order.payment_method == Order.PAYMENT_PIX:
        return redirect('payment_pix', order_number=order.order_number)
    return redirect('payment_link', order_number=order.order_number)


@login_required
@require_POST
def change_payment_method(request, order_number):
    order = get_object_or_404(
        Order.objects.filter(customer=request.user),
        order_number=order_number,
    )
    if not order.can_retry_payment:
        messages.error(request, 'Este pedido não permite alteração de pagamento.')
        return redirect('order_detail', order_number=order.order_number)

    new_method = request.POST.get('payment_method', '')
    valid_methods = {value for value, _ in Order.PAYMENT_CHOICES}
    if new_method not in valid_methods:
        messages.error(request, 'Método de pagamento inválido.')
        return redirect('order_detail', order_number=order.order_number)

    order.payment_method = new_method
    order.save(update_fields=['payment_method', 'updated_at'])

    service = PaymentService()
    service.create_payment(order, force_new=True)

    if new_method == Order.PAYMENT_PIX:
        return redirect('payment_pix', order_number=order.order_number)
    return redirect('payment_link', order_number=order.order_number)


@csrf_exempt
@require_POST
def webhook_mercadopago(request):
    content_length = int(request.META.get('CONTENT_LENGTH') or 0)
    if content_length > MAX_WEBHOOK_BYTES:
        return HttpResponse(status=413)
    service = PaymentService()
    return HttpResponse(status=service.confirm_payment_webhook('mercadopago', request))
