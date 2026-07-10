from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
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
