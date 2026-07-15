from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.shortcuts import render
from django.utils.crypto import constant_time_compare
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView
from products.models import Product, Category
from .services import update_all_exchange_rates_from_api
from .models import ExchangeRate, NextTrip, ShowcaseSlide, StoreSettings


def home(request):
    _base_qs = Product.objects.filter(is_active=True).select_related('category', 'brand_fk').prefetch_related('images')
    featured = _base_qs.filter(is_featured=True).order_by('-created_at')[:8]
    on_sale = _base_qs.filter(is_on_sale=True).order_by('-created_at')[:8]
    in_stock = _base_qs.filter(status='available').order_by('-created_at')[:8]
    pre_order = _base_qs.filter(is_pre_order=True).order_by('-created_at')[:8]
    hero_products = _base_qs.order_by('-is_featured', '-created_at')[:3]
    hero_perfumes = _base_qs.filter(category__slug__in=['perfumes', 'decanter']).order_by('-is_featured', '-created_at')[:3]
    hero_kbeauty = _base_qs.filter(category__slug='beleza-coreana').order_by('-is_featured', '-created_at')[:3]
    new_arrivals = _base_qs.order_by('-created_at')[:6]
    categories = Category.objects.filter(is_active=True)
    next_trip = NextTrip.objects.filter(is_active=True).first()
    current_exchange_rate = ExchangeRate.objects.filter(is_active=True).order_by('-updated_at').first()
    try:
        showcase_slides = list(
            ShowcaseSlide.objects.filter(is_active=True).select_related('product')[:ShowcaseSlide.MAX_SLIDES]
        )
    except Exception:
        showcase_slides = []

    return render(request, 'home.html', {
        'featured': featured,
        'on_sale': on_sale,
        'in_stock': in_stock,
        'pre_order': pre_order,
        'hero_products': hero_products,
        'hero_perfumes': hero_perfumes,
        'hero_kbeauty': hero_kbeauty,
        'new_arrivals': new_arrivals,
        'categories': categories,
        'next_trip': next_trip,
        'current_exchange_rate': current_exchange_rate,
        'showcase_slides': showcase_slides,
    })


def about(request):
    return render(request, 'pages/about.html')


def contact(request):
    store = StoreSettings.get_settings()
    return render(request, 'pages/contact.html', {'store': store})


def next_trip_page(request):
    next_trip = NextTrip.objects.filter(is_active=True).first()
    pre_order_products = Product.objects.filter(is_active=True, is_pre_order=True).order_by('-created_at')
    return render(request, 'pages/next_trip.html', {
        'next_trip': next_trip,
        'pre_order_products': pre_order_products,
    })


def privacy_policy(request):
    return render(request, 'pages/privacy.html')


def return_policy(request):
    return render(request, 'pages/returns.html')


def shipping_policy(request):
    return render(request, 'pages/shipping_policy.html')


def pre_order_terms(request):
    return render(request, 'pages/pre_order_terms.html')


def payment_methods(request):
    return render(request, 'pages/payment_methods.html')


@never_cache
@require_GET
def update_exchange_rates_cron(request):
    expected_secret = getattr(settings, 'CRON_SECRET', '')
    authorization = request.headers.get('Authorization', '')
    expected_header = f'Bearer {expected_secret}'
    if not expected_secret or not constant_time_compare(authorization, expected_header):
        return JsonResponse({'ok': False, 'error': 'Nao autorizado.'}, status=401)

    try:
        rates = update_all_exchange_rates_from_api()
    except Exception as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=502)

    return JsonResponse({
        'ok': True,
        'updated': [
            {
                'pair': f'{rate.currency_from}-{rate.currency_to}',
                'rate': str(rate.rate),
                'source': rate.source,
                'updated_at': rate.updated_at.isoformat(),
            }
            for rate in rates
        ],
    })
