from django.shortcuts import render
from django.views.generic import TemplateView
from products.models import Product, Category
from .models import ExchangeRate, NextTrip, StoreSettings


def home(request):
    featured = Product.objects.filter(is_active=True, is_featured=True).order_by('-created_at')[:8]
    on_sale = Product.objects.filter(is_active=True, is_on_sale=True).order_by('-created_at')[:8]
    in_stock = Product.objects.filter(is_active=True, status='available').order_by('-created_at')[:8]
    pre_order = Product.objects.filter(is_active=True, is_pre_order=True).order_by('-created_at')[:8]
    hero_products = Product.objects.filter(is_active=True).select_related('category').prefetch_related('images').order_by('-is_featured', '-created_at')[:3]
    hero_perfumes = Product.objects.filter(is_active=True, category__slug__in=['perfumes', 'decanter']).select_related('category').prefetch_related('images').order_by('-is_featured', '-created_at')[:3]
    hero_kbeauty = Product.objects.filter(is_active=True, category__slug='beleza-coreana').select_related('category').prefetch_related('images').order_by('-is_featured', '-created_at')[:3]
    categories = Category.objects.filter(is_active=True)
    next_trip = NextTrip.objects.filter(is_active=True).first()
    current_exchange_rate = ExchangeRate.objects.filter(is_active=True).order_by('-updated_at').first()

    return render(request, 'home.html', {
        'featured': featured,
        'on_sale': on_sale,
        'in_stock': in_stock,
        'pre_order': pre_order,
        'hero_products': hero_products,
        'hero_perfumes': hero_perfumes,
        'hero_kbeauty': hero_kbeauty,
        'categories': categories,
        'next_trip': next_trip,
        'current_exchange_rate': current_exchange_rate,
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
