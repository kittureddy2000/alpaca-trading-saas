"""Authentication URL routes."""

from django.urls import path
from django.views.generic import RedirectView
from trading_api.views.auth import (
    RegisterView,
    LoginView,
    LogoutView,
    CurrentUserView,
    GoogleCallbackView,
    GoogleLoginCallbackView,
)

urlpatterns = [
    path('register', RegisterView.as_view(), name='register'),
    path('login', LoginView.as_view(), name='login'),
    path('logout', LogoutView.as_view(), name='logout'),
    path('me', CurrentUserView.as_view(), name='current-user'),
    path('google/callback', GoogleCallbackView.as_view(), name='google-callback'),
    path('google/token', GoogleLoginCallbackView.as_view(), name='google-token-callback'),
    path('google', RedirectView.as_view(url='/accounts/google/login/', permanent=False), name='google-login'),
]
