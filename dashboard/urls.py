from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_home, name='home'),
    path('produtos/', views.product_list, name='products'),
    path('produtos/novo/', views.product_add, name='product_add'),
    path('produtos/<int:pk>/editar/', views.product_edit, name='product_edit'),
    path('produtos/<int:pk>/excluir/', views.product_delete, name='product_delete'),
    path('produtos/imagem/<int:pk>/principal/', views.image_set_main, name='image_set_main'),
    path('produtos/imagem/<int:pk>/excluir/', views.image_delete, name='image_delete'),
    path('pedidos/', views.order_list, name='orders'),
    path('pedidos/<int:pk>/', views.order_detail, name='order_detail'),
    path('clientes/', views.customer_list, name='customers'),
    path('encomendas/', views.pre_order_list, name='pre_orders'),
    path('proxima-viagem/', views.next_trip_edit, name='next_trip'),
    path('configuracoes/', views.store_settings, name='settings'),
    path('relatorios/', views.reports_view, name='reports'),
    path('categorias/', views.category_list, name='categories'),
    path('categorias/nova/', views.category_edit, name='category_add'),
    path('categorias/<int:pk>/editar/', views.category_edit, name='category_edit'),
    path('api/gtin/', views.gtin_lookup, name='gtin_lookup'),
    path('api/image-search/', views.image_search, name='image_search'),
    path('produtos/<int:pk>/imagem-url/', views.image_from_url, name='image_from_url'),
]
