from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings as django_settings
from django.urls import reverse

from orders.models import Order
from orders.services import order_queryset_for_user
from .services import PaymentService


MAX_WEBHOOK_BYTES = 64 * 1024


def _require_online_payment_method(request, order):
    if order.payment_method != Order.PAYMENT_WHATSAPP:
        return None
    messages.info(request, 'Escolha Pix ou cartão para continuar o pagamento.')
    return redirect('order_detail', order_number=order.order_number)


@login_required
def payment_pix(request, order_number):
    order = get_object_or_404(order_queryset_for_user(request.user), order_number=order_number)
    if order.payment_status == Order.PAYMENT_STATUS_CONFIRMED:
        return redirect('order_detail', order_number=order.order_number)
    if order.payment_status == Order.PAYMENT_STATUS_REFUNDED:
        messages.info(request, 'Este pagamento foi estornado. Consulte os detalhes do pedido.')
        return redirect('order_detail', order_number=order.order_number)
    redirect_response = _require_online_payment_method(request, order)
    if redirect_response:
        return redirect_response
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
    if order.payment_status == Order.PAYMENT_STATUS_CONFIRMED:
        return redirect('order_detail', order_number=order.order_number)
    if order.payment_status == Order.PAYMENT_STATUS_REFUNDED:
        messages.info(request, 'Este pagamento foi estornado. Consulte os detalhes do pedido.')
        return redirect('order_detail', order_number=order.order_number)
    redirect_response = _require_online_payment_method(request, order)
    if redirect_response:
        return redirect_response
    service = PaymentService()
    payment = service.create_payment(order)
    return render(request, 'checkout/payment_link.html', {
        'order': order,
        'payment': payment,
        'payment_is_simulated': getattr(django_settings, 'PAYMENT_SANDBOX', True),
    })


@login_required
@require_GET
def payment_status(request, order_number):
    order = get_object_or_404(order_queryset_for_user(request.user), order_number=order_number)
    if (
        order.payment_method != Order.PAYMENT_WHATSAPP
        and order.payment_status in (Order.PAYMENT_STATUS_PENDING, '')
    ):
        payment_id = request.GET.get('payment_id', '')
        if not payment_id.isdigit():
            payment_id = ''
        PaymentService().sync_order_payment(order, payment_id=payment_id)
        order.refresh_from_db(fields=['payment_status', 'status', 'payment_confirmed_at'])

    paid = order.payment_status == Order.PAYMENT_STATUS_CONFIRMED
    refunded = order.payment_status == Order.PAYMENT_STATUS_REFUNDED
    return JsonResponse({
        'paid': paid,
        'terminal': paid or refunded,
        'payment_status': order.payment_status,
        'message': (
            'Pagamento confirmado.' if paid
            else 'Pagamento estornado.' if refunded
            else 'Aguardando confirmação do pagamento.'
        ),
        'redirect_url': reverse('order_detail', args=[order.order_number]),
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
    if not (order.can_retry_payment or order.can_choose_online_payment):
        messages.error(request, 'Este pedido não permite alteração de pagamento.')
        return redirect('order_detail', order_number=order.order_number)

    new_method = request.POST.get('payment_method', '')
    valid_methods = {Order.PAYMENT_PIX, Order.PAYMENT_CREDIT_CARD}
    if new_method not in valid_methods:
        messages.error(request, 'Método de pagamento inválido.')
        return redirect('order_detail', order_number=order.order_number)

    order.payment_method = new_method
    if order.status in {Order.STATUS_CREATED, Order.STATUS_AWAITING_CONTACT}:
        order.status = Order.STATUS_AWAITING_PAYMENT
    order.save(update_fields=['payment_method', 'status', 'updated_at'])

    service = PaymentService()
    service.create_payment(order, force_new=True)

    if new_method == Order.PAYMENT_PIX:
        return redirect('payment_pix', order_number=order.order_number)
    return redirect('payment_link', order_number=order.order_number)


@csrf_exempt
@require_POST
def webhook_mercadopago(request):
    try:
        content_length = int(request.META.get('CONTENT_LENGTH') or 0)
    except (TypeError, ValueError):
        return HttpResponse(status=400)
    if content_length > MAX_WEBHOOK_BYTES:
        return HttpResponse(status=413)
    service = PaymentService()
    return HttpResponse(status=service.confirm_payment_webhook('mercadopago', request))
