from django.urls import path
from . import views

urlpatterns = [
    path('cadastro/', views.register, name='register'),
    path('entrar/', views.login_view, name='login'),
    path('sair/', views.logout_view, name='logout'),
    path('perfil/', views.profile, name='profile'),
    path('meus-pedidos/', views.my_orders, name='my_orders'),
    path('meus-pedidos/<str:order_number>/', views.order_detail, name='order_detail'),
]
