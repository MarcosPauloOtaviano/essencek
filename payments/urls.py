from django.urls import path
from . import views

urlpatterns = [
    path('pix/<str:order_number>/', views.payment_pix, name='payment_pix'),
    path('link/<str:order_number>/', views.payment_link, name='payment_link'),
    path('tentar-novamente/<str:order_number>/', views.retry_payment, name='retry_payment'),
    path('alterar-metodo/<str:order_number>/', views.change_payment_method, name='change_payment_method'),
    path('webhook/mercadopago/', views.webhook_mercadopago, name='webhook_mp'),
]
