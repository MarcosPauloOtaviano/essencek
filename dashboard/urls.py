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
    path('marcas/', views.brand_list, name='brands'),
    path('marcas/nova/', views.brand_edit, name='brand_add'),
    path('marcas/<int:pk>/editar/', views.brand_edit, name='brand_edit'),
    path('marcas/<int:pk>/excluir/', views.brand_delete, name='brand_delete'),
    path('showcase/', views.showcase_list, name='showcase'),
    path('showcase/produtos/buscar/', views.showcase_product_search, name='showcase_product_search'),
    path('showcase/produtos/adicionar/', views.showcase_add_products, name='showcase_add_products'),
    path('showcase/texto/novo/', views.showcase_text_add, name='showcase_text_add'),
    path('showcase/<int:pk>/editar/', views.showcase_edit, name='showcase_edit'),
    path('showcase/<int:pk>/excluir/', views.showcase_delete, name='showcase_delete'),
    path('showcase/<int:pk>/mover/<str:direction>/', views.showcase_move, name='showcase_move'),
    path('showcase/<int:pk>/ativo/', views.showcase_toggle_active, name='showcase_toggle_active'),
    path('api/gtin/', views.gtin_lookup, name='gtin_lookup'),
    path('api/image-search/', views.image_search, name='image_search'),
    path('produtos/<int:pk>/imagem-url/', views.image_from_url, name='image_from_url'),
]
