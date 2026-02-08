"""URL Configuration for Alpaca Trading SaaS."""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/', include('trading_api.urls.auth')),
    path('api/', include('trading_api.urls.api')),
    path('accounts/', include('allauth.urls')),
]
