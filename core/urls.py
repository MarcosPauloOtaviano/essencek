from django.urls import path
from . import views
from products.views import product_list

urlpatterns = [
    path('', views.home, name='home'),
    path('ofertas/', product_list, {'quick_filter': 'ofertas'}, name='offers'),
    path('destaques/', product_list, {'quick_filter': 'destaques'}, name='featured_products'),
    path('pronta-entrega/', product_list, {'quick_filter': 'pronta-entrega'}, name='available_products'),
    path('categoria/<slug:category_key>/', product_list, name='category_landing'),
    path('sobre/', views.about, name='about'),
    path('contato/', views.contact, name='contact'),
    path('proxima-viagem/', views.next_trip_page, name='next_trip'),
    path('politica-de-privacidade/', views.privacy_policy, name='privacy'),
    path('trocas-e-devolucoes/', views.return_policy, name='returns'),
    path('prazos-de-entrega/', views.shipping_policy, name='shipping_policy'),
    path('termos-de-encomenda/', views.pre_order_terms, name='pre_order_terms'),
    path('formas-de-pagamento/', views.payment_methods, name='payment_methods'),
    path('cron/update-exchange-rate/', views.update_exchange_rates_cron, name='cron_update_exchange_rates'),
]
