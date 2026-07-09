from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from two_factor.urls import urlpatterns as tf_urls

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('conta/', include('accounts.urls')),
    path('produtos/', include('products.urls')),
    path('carrinho/', include('cart.urls')),
    path('checkout/', include('orders.urls')),
    path('pagamento/', include('payments.urls')),
    path('painel/', include('dashboard.urls')),
    path('conta/2fa/', include(tf_urls)),
]

if getattr(settings, 'SERVE_MEDIA_FILES', False):
    from core.media_views import serve_media_file

    urlpatterns += [
        re_path(
            r'^media/(?P<path>.*)$',
            serve_media_file,
        ),
    ]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
