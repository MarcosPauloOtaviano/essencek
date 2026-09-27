from django.db.models import Sum, Count, F, Avg, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncMonth
from datetime import timedelta

from orders.models import Order, OrderItem, PreOrderRequest
from products.models import Product


def _gross_profit_for_orders(orders_qs):
    paid_items = OrderItem.objects.filter(
        order__in=orders_qs,
        product__cost_price__isnull=False,
    ).select_related('product')
    return sum(
        (item.unit_price - item.product.cost_price) * item.quantity
        for item in paid_items if item.product and item.product.cost_price
    )


def _stock_values():
    invested = Product.objects.filter(
        is_active=True, cost_price__isnull=False, stock__gt=0,
    ).aggregate(
        total=Sum(ExpressionWrapper(F('cost_price') * F('stock'), output_field=DecimalField()))
    )['total'] or 0

    potential = Product.objects.filter(
        is_active=True, stock__gt=0,
    ).aggregate(
        total=Sum(ExpressionWrapper(F('price') * F('stock'), output_field=DecimalField()))
    )['total'] or 0

    return invested, potential


def get_dashboard_summary(now):
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    monthly_orders = Order.objects.filter(
        payment_status=Order.PAYMENT_STATUS_CONFIRMED,
        payment_confirmed_at__gte=start_of_month,
    )
    monthly_revenue = monthly_orders.aggregate(total=Sum('total'))['total'] or 0
    gross_profit = _gross_profit_for_orders(monthly_orders)

    awaiting_payment = Order.objects.filter(
        payment_status__in=[Order.PAYMENT_STATUS_PENDING, ''],
    ).exclude(status=Order.STATUS_CANCELLED).count()
    paid_orders = Order.objects.filter(
        payment_status=Order.PAYMENT_STATUS_CONFIRMED,
    ).count()

    active_products = Product.objects.filter(is_active=True).count()
    out_of_stock = Product.objects.filter(status='out_of_stock', is_active=True).count()
    pre_order_count = Product.objects.filter(is_pre_order=True, is_active=True).count()
    low_stock = Product.objects.filter(stock__gt=0, stock__lte=3, is_active=True).count()

    stock_value, potential_value = _stock_values()

    six_months_ago = now - timedelta(days=180)
    monthly_sales = (
        Order.objects.filter(
            payment_confirmed_at__gte=six_months_ago,
            payment_status=Order.PAYMENT_STATUS_CONFIRMED,
        )
        .annotate(month=TruncMonth('payment_confirmed_at'))
        .values('month')
        .annotate(revenue=Sum('total'), count=Count('id'))
        .order_by('month')
    )
    chart_labels = [m['month'].strftime('%b/%Y') for m in monthly_sales]
    chart_revenue = [float(m['revenue']) for m in monthly_sales]

    top_products = (
        OrderItem.objects.filter(order__payment_status=Order.PAYMENT_STATUS_CONFIRMED)
        .values('product_name')
        .annotate(total_sold=Sum('quantity'))
        .order_by('-total_sold')[:5]
    )

    open_pre_orders = PreOrderRequest.objects.exclude(
        status__in=['delivered', 'cancelled'],
    ).count()

    return {
        'monthly_revenue': monthly_revenue,
        'gross_profit': gross_profit,
        'awaiting_payment': awaiting_payment,
        'paid_orders': paid_orders,
        'active_products': active_products,
        'out_of_stock': out_of_stock,
        'pre_order_count': pre_order_count,
        'low_stock': low_stock,
        'stock_value': stock_value,
        'potential_value': potential_value,
        'chart_labels': chart_labels,
        'chart_revenue': chart_revenue,
        'top_products': top_products,
        'open_pre_orders': open_pre_orders,
    }


def get_reports_data(now):
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    monthly_orders = Order.objects.filter(
        payment_status=Order.PAYMENT_STATUS_CONFIRMED,
        payment_confirmed_at__gte=start_of_month,
    )

    revenue_month = monthly_orders.aggregate(total=Sum('total'))['total'] or 0
    avg_ticket = monthly_orders.aggregate(avg=Avg('total'))['avg'] or 0
    gross_profit = _gross_profit_for_orders(monthly_orders)

    top_products = (
        OrderItem.objects.filter(order__in=monthly_orders)
        .values('product_name')
        .annotate(qty=Sum('quantity'), revenue=Sum(F('unit_price') * F('quantity')))
        .order_by('-qty')[:10]
    )

    sales_by_category = (
        OrderItem.objects.filter(
            order__in=monthly_orders,
            product__isnull=False,
        )
        .values('product__category__name')
        .annotate(revenue=Sum(F('unit_price') * F('quantity')))
        .order_by('-revenue')
    )

    stock_value, potential_value = _stock_values()

    products_margin = Product.objects.filter(
        is_active=True, cost_price__isnull=False, price__gt=0,
    ).annotate(
        margin=ExpressionWrapper(
            (F('price') - F('cost_price')) / F('price') * 100,
            output_field=DecimalField(),
        )
    ).order_by('-margin')[:10]

    pending_payments = Order.objects.filter(
        payment_status__in=[Order.PAYMENT_STATUS_PENDING, ''],
    ).exclude(status=Order.STATUS_CANCELLED)
    pending_orders = pending_payments.count()
    pending_amount = pending_payments.aggregate(total=Sum('total'))['total'] or 0

    refunded_orders = Order.objects.filter(
        payment_status=Order.PAYMENT_STATUS_REFUNDED,
    )
    refunded_count = refunded_orders.count()
    refunded_amount = refunded_orders.aggregate(total=Sum('total'))['total'] or 0
    open_pre_orders = PreOrderRequest.objects.exclude(
        status__in=['delivered', 'cancelled'],
    ).count()

    chart_cat_labels = [c['product__category__name'] or 'Sem categoria' for c in sales_by_category]
    chart_cat_data = [float(c['revenue']) for c in sales_by_category]

    return {
        'revenue_month': revenue_month,
        'gross_profit': gross_profit,
        'avg_ticket': avg_ticket,
        'paid_orders_month': monthly_orders.count(),
        'stock_value': stock_value,
        'potential_value': potential_value,
        'top_products': top_products,
        'products_margin': products_margin,
        'pending_orders': pending_orders,
        'pending_amount': pending_amount,
        'refunded_count': refunded_count,
        'refunded_amount': refunded_amount,
        'open_pre_orders': open_pre_orders,
        'recent_orders': Order.objects.select_related('customer').order_by('-updated_at')[:20],
        'chart_cat_labels': chart_cat_labels,
        'chart_cat_data': chart_cat_data,
    }
