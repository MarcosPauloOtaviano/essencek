from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('', views.checkout, name='checkout'),
    path('sucesso/<str:order_number>/', views.order_success, name='success'),
]
