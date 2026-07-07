from django.urls import path
from . import views

app_name = 'cart'

urlpatterns = [
    path('', views.cart_detail, name='detail'),
    path('adicionar/<int:product_id>/', views.cart_add, name='add'),
    path('atualizar/<int:item_id>/', views.cart_update, name='update'),
    path('remover/<int:item_id>/', views.cart_remove, name='remove'),
    path('calcular-frete/', views.calculate_shipping_view, name='shipping'),
    path('selecionar-frete/', views.select_shipping_view, name='select_shipping'),
]
