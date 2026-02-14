# Login with Google - Complete Implementation Guide

A comprehensive, step-by-step framework for implementing Google OAuth login in a **Django + React SPA** deployed on **Google Cloud Run**. This guide documents every file, configuration, and lesson learned so you can replicate this in any new project.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Prerequisites - Google Cloud Console Setup](#2-prerequisites---google-cloud-console-setup)
3. [Backend Setup (Django)](#3-backend-setup-django)
   - 3.1 [Python Dependencies](#31-python-dependencies)
   - 3.2 [Django Settings - Base](#32-django-settings---base)
   - 3.3 [Django Settings - Production](#33-django-settings---production)
   - 3.4 [User Model](#34-user-model)
   - 3.5 [Authentication Views](#35-authentication-views)
   - 3.6 [URL Routing](#36-url-routing)
   - 3.7 [Allauth Adapters](#37-allauth-adapters)
   - 3.8 [Google OAuth Setup Script](#38-google-oauth-setup-script)
   - 3.9 [Entrypoint Script](#39-entrypoint-script)
4. [Frontend Setup (React)](#4-frontend-setup-react)
   - 4.1 [npm Dependencies](#41-npm-dependencies)
   - 4.2 [GoogleOAuthProvider Wrapper](#42-googleoauthprovider-wrapper)
   - 4.3 [API Module - Token Management](#43-api-module---token-management)
   - 4.4 [GoogleLogin Component](#44-googlelogin-component)
   - 4.5 [CSS Styling](#45-css-styling)
5. [Infrastructure & Deployment](#5-infrastructure--deployment)
   - 5.1 [Frontend Dockerfile](#51-frontend-dockerfile)
   - 5.2 [Nginx Configuration](#52-nginx-configuration)
   - 5.3 [Backend Dockerfile](#53-backend-dockerfile)
   - 5.4 [Docker Compose (Local Dev)](#54-docker-compose-local-dev)
   - 5.5 [CI/CD - GitHub Actions](#55-cicd---github-actions)
6. [Environment Variables Reference](#6-environment-variables-reference)
7. [Data Flow - Step by Step](#7-data-flow---step-by-step)
8. [Lessons Learned & Pitfalls](#8-lessons-learned--pitfalls)

---

## 1. Architecture Overview

### Flow Diagram

```
  User's Browser                    Frontend (React SPA)              Backend (Django API)           Google
  ============                      ===================               ===================           ======

  1. Click "Sign in                 2. @react-oauth/google
     with Google"  ───────────────>    opens Google popup  ─────────────────────────────────────>  3. Google login
                                                                                                      screen

                                    4. Receives Google
                                       ID token (JWT)   <──────────────────────────────────────  Google returns
                                                                                                    ID token

                                    5. POST /auth/google/token  ──>  6. Verify token with
                                       { token: "eyJ..." }              Google's public keys
                                                                     7. Extract email, name,
                                                                        picture from token
                                                                     8. Create or update User
                                                                     9. Generate JWT tokens
                                                                        (access + refresh)

                                    10. Store JWT tokens  <────────  11. Return { tokens,
                                        in localStorage                   authenticated: true }

  12. Dashboard loads
      with user data  <────────    All API calls include
                                    Authorization: Bearer <token>
```

### Why Frontend-Driven (Not Server-Side Redirect)?

The traditional allauth server-side redirect flow (`/accounts/google/login/` -> Google -> `/accounts/google/login/callback/`) **breaks on Cloud Run** because:

1. **Cross-domain session cookie loss**: The backend (`api.example.com`) sets a session cookie during OAuth initiation. When Google redirects back, the cookie may not be sent if `SESSION_COOKIE_DOMAIN` doesn't match, or if `SameSite` restrictions apply.

2. **Stateless containers**: Cloud Run spins up new containers per request. If using in-memory sessions (default), the session created during OAuth initiation may not exist when the callback arrives on a different container instance.

3. **SPA architecture**: The frontend and backend are on different domains (`app.example.com` vs `api.example.com`), making cross-domain cookie management fragile.

**Frontend-driven flow eliminates all three issues**: The Google popup runs entirely in the browser, the ID token is sent directly to the backend in a single POST request (no session needed), and JWT tokens are returned in the response body (no cookies needed).

---

## 2. Prerequisites - Google Cloud Console Setup

### Step 1: Create OAuth Consent Screen

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **APIs & Services > OAuth consent screen**
3. Select **External** user type
4. Fill in:
   - App name: Your app name
   - User support email: Your email
   - Authorized domains: `samaanai.com` (your top-level domain)
   - Developer contact email: Your email
5. Add scopes: `email`, `profile`, `openid`
6. Add test users (while in "Testing" status)
7. Publish the app when ready for production

### Step 2: Create OAuth Credentials

1. Navigate to **APIs & Services > Credentials**
2. Click **Create Credentials > OAuth 2.0 Client IDs**
3. Application type: **Web application**
4. Name: e.g., "Alpaca Trading SaaS"
5. **Authorized JavaScript origins** (critical for frontend-driven flow):
   ```
   https://stg.alpaca.samaanai.com
   https://alpaca.samaanai.com
   http://localhost:5173          (for local dev)
   http://localhost:3000          (alternative local dev port)
   ```
6. **Authorized redirect URIs** (for allauth fallback):
   ```
   https://api.stg.alpaca.samaanai.com/accounts/google/login/callback/
   https://api.alpaca.samaanai.com/accounts/google/login/callback/
   http://localhost:8000/accounts/google/login/callback/
   ```
7. Save and note the **Client ID** and **Client Secret**

### Step 3: Store Credentials as Secrets

In GitHub Actions secrets (or your CI/CD system):
- `GOOGLE_CLIENT_ID` = the Client ID from step 2
- `GOOGLE_CLIENT_SECRET` = the Client Secret from step 2

---

## 3. Backend Setup (Django)

### 3.1 Python Dependencies

**File**: `requirements.txt`

```
# Core Django
Django>=4.2.0
djangorestframework>=3.14.0

# JWT Authentication
djangorestframework-simplejwt>=5.3.0

# CORS (required for cross-domain SPA)
django-cors-headers>=4.3.0

# OAuth Framework (handles SocialApp model, account linking)
django-allauth>=0.57.0

# Google token verification
google-auth>=2.0.0

# Server
gunicorn>=21.0.0
whitenoise>=6.6.0
```

**Key packages explained**:
- `django-allauth`: Provides the `SocialApp` model for storing OAuth credentials in the database, the `SocialAccount` model for linking Google accounts to users, and the adapter pattern for customizing behavior. Even though we use frontend-driven OAuth, allauth is still used for credential storage and account linking.
- `google-auth`: Provides `google.oauth2.id_token.verify_oauth2_token()` which verifies the Google ID token's signature against Google's public keys and validates the `aud` (audience) claim matches your Client ID.
- `djangorestframework-simplejwt`: Generates JWT access/refresh tokens for API authentication after Google login.

### 3.2 Django Settings - Base

**File**: `backend/settings/base.py`

#### INSTALLED_APPS

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',          # Required by allauth
    'allauth',                       # OAuth framework
    'allauth.account',               # Account management
    'allauth.socialaccount',         # Social account management
    'allauth.socialaccount.providers.google',  # Google provider
    'rest_framework',                # DRF
    'rest_framework_simplejwt.token_blacklist',  # JWT token blacklisting
    'corsheaders',                   # CORS headers
    'trading_api',                   # Your app
]
```

#### MIDDLEWARE

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',      # Must be before CommonMiddleware
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',  # Required by allauth
]
```

#### Sites Framework

```python
# Required by allauth - references the Site object in the database
SITE_ID = 1
```

#### REST Framework Configuration

```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',  # Required for allauth OAuth
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}
```

#### JWT Settings

```python
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=24),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,        # Issue new refresh token on each refresh
    'BLACKLIST_AFTER_ROTATION': True,      # Blacklist old refresh token
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),      # Authorization: Bearer <token>
}
```

#### Allauth Settings

```python
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',          # Default Django auth
    'allauth.account.auth_backends.AuthenticationBackend', # Allauth (Google etc.)
]

# Account behavior
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_VERIFICATION = 'none'          # Skip email verification for OAuth
ACCOUNT_USER_MODEL_USERNAME_FIELD = None      # Custom user model has no username
ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https'       # Always HTTPS for OAuth callbacks

# Custom adapters (see Section 3.7)
ACCOUNT_ADAPTER = 'trading_api.adapters.CustomAccountAdapter'
SOCIALACCOUNT_ADAPTER = 'trading_api.adapters.CustomSocialAccountAdapter'

# Social account behavior
SOCIALACCOUNT_STORE_TOKENS = True
SOCIALACCOUNT_AUTO_SIGNUP = True              # Auto-create user on first Google login
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_LOGIN_ON_GET = True             # Allow OAuth login on GET request
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True  # Auto-link by email

# Google provider config
# IMPORTANT: Do NOT put APP credentials here - store them in database via SocialApp model
# Having credentials in BOTH settings and database causes MultipleObjectsReturned errors
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    }
}
```

#### CORS Settings (Base)

```python
CORS_ALLOWED_ORIGINS = os.environ.get(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173'
).split(',')
CORS_ALLOW_CREDENTIALS = True    # Allow cookies in cross-origin requests
```

#### Frontend URL

```python
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:5173')
LOGIN_REDIRECT_URL = os.environ.get('LOGIN_REDIRECT_URL', '/auth/callback')
```

### 3.3 Django Settings - Production

**File**: `backend/settings/production.py`

```python
import os
from .base import *

DEBUG = False

# Allowed hosts - hardcode known domains + parse env var
ALLOWED_HOSTS = [host.strip() for host in os.environ.get('ALLOWED_HOSTS', '').replace(',', ' ').split() if host.strip()]

# Always include known production/staging domains
CLOUD_RUN_HOSTS = [
    'alpaca.samaanai.com',
    'api.alpaca.samaanai.com',
    'stg.alpaca.samaanai.com',
    'api.stg.alpaca.samaanai.com',
    '.run.app',  # Wildcard for all Cloud Run URLs
]
for host in CLOUD_RUN_HOSTS:
    if host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)

# CORS - hardcode known origins
CORS_ALLOWED_ORIGINS = [
    'https://alpaca.samaanai.com',
    'https://api.alpaca.samaanai.com',
    'https://stg.alpaca.samaanai.com',
    'https://api.stg.alpaca.samaanai.com',
]
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://alpaca-.*\.run\.app$",  # Cloud Run service URLs
]

# Add FRONTEND_URL to CORS
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://alpaca.samaanai.com')
if FRONTEND_URL not in CORS_ALLOWED_ORIGINS:
    CORS_ALLOWED_ORIGINS.append(FRONTEND_URL)

# Security settings
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Session cookies - env-configurable for staging vs production
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_NAME = 'sessionid_v2'
SESSION_COOKIE_SAMESITE = 'None'       # Required for cross-domain OAuth redirects
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_DOMAIN = os.environ.get('SESSION_COOKIE_DOMAIN', '.alpaca.samaanai.com')
SESSION_SAVE_EVERY_REQUEST = True
SESSION_ENGINE = 'django.contrib.sessions.backends.db'  # Database sessions for stateless containers

# CSRF settings
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_DOMAIN = os.environ.get('CSRF_COOKIE_DOMAIN', '.alpaca.samaanai.com')

# CSRF trusted origins
CSRF_TRUSTED_ORIGINS = [
    'https://alpaca.samaanai.com',
    'https://api.alpaca.samaanai.com',
    'https://stg.alpaca.samaanai.com',
    'https://api.stg.alpaca.samaanai.com',
    'https://*.run.app',
    'https://accounts.google.com',  # Google OAuth callback
]
```

### 3.4 User Model

**File**: `trading_api/models/user.py`

The User model includes fields to support Google OAuth:

```python
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()  # Google OAuth users don't need passwords
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    # Google OAuth fields
    google_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    auth_provider = models.CharField(
        max_length=10,
        choices=[('local', 'Local'), ('google', 'Google'), ('both', 'Both')],
        default='local'
    )
    email_verified = models.BooleanField(default=False)
    picture_url = models.URLField(max_length=500, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def update_last_login(self):
        self.last_login = timezone.now()
        self.save(update_fields=['last_login'])
```

**Key design decisions**:
- `google_id`: Stores Google's `sub` claim (unique per Google account). Used for fast lookup.
- `auth_provider`: Tracks how the user signed up. `'both'` means they registered with email/password AND later linked Google.
- `email_verified`: Set to `True` for Google users (Google verifies emails).
- `picture_url`: Stores Google profile picture URL.
- `set_unusable_password()`: Google-only users don't have passwords.

### 3.5 Authentication Views

**File**: `trading_api/views/auth.py`

This is the core of the Google login implementation. The `GoogleLoginCallbackView` handles the frontend-driven flow.

```python
import os
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from trading_api.models import User, UserSettings, UserSubscription

logger = logging.getLogger(__name__)


def get_tokens_for_user(user):
    """Generate JWT access + refresh tokens for a user."""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


class GoogleLoginCallbackView(APIView):
    """Handle frontend-driven Google OAuth token verification.

    Receives a Google ID token from the frontend @react-oauth/google component,
    verifies it with Google's public keys, creates/updates the user, and returns
    JWT tokens for subsequent API authentication.
    """

    permission_classes = [AllowAny]
    authentication_classes = [JWTAuthentication]  # See "Lessons Learned" section

    def post(self, request):
        token = request.data.get('token')

        if not token:
            return Response(
                {'error': 'Token is required'},
                status=400
            )

        try:
            # 1. Get Google Client ID
            # Try environment variable first, then database SocialApp as fallback
            client_id = os.environ.get('GOOGLE_CLIENT_ID', '')

            if not client_id:
                try:
                    from allauth.socialaccount.models import SocialApp
                    app = SocialApp.objects.filter(provider='google').first()
                    if app:
                        client_id = app.client_id
                except Exception:
                    pass

            if not client_id:
                logger.error("Google client ID not configured in env or database")
                return Response(
                    {'error': 'Google OAuth not configured'},
                    status=500
                )

            # 2. Verify the Google ID token
            # This checks: signature (against Google's public keys), expiry, aud (must match client_id)
            id_info = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                client_id
            )

            # 3. Extract user info from verified token
            email = id_info.get('email', '').lower()
            name = id_info.get('name', '')
            picture = id_info.get('picture', '')
            google_id = id_info.get('sub', '')  # Google's unique user ID

            if not email:
                return Response(
                    {'error': 'Email not provided by Google'},
                    status=400
                )

            # 4. Get or create user
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'name': name or email.split('@')[0],
                    'picture_url': picture,
                    'google_id': google_id,
                    'auth_provider': 'google',
                    'email_verified': True,
                    'is_active': True,
                }
            )

            if not created:
                # Update existing user with Google info (if not already set)
                if not user.name and name:
                    user.name = name
                if not user.picture_url and picture:
                    user.picture_url = picture
                if not user.google_id:
                    user.google_id = google_id
                if user.auth_provider == 'local':
                    user.auth_provider = 'both'  # User had email/password, now also has Google
                user.email_verified = True
                user.save()

            # 5. Ensure related objects exist
            UserSettings.objects.get_or_create(user=user)
            UserSubscription.objects.get_or_create(
                user=user,
                defaults={'tier': 'free', 'status': 'active'}
            )

            # 6. Update last login timestamp
            user.update_last_login()

            # 7. Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            logger.info(f"Google login {'created' if created else 'updated'} user: {email}")

            return Response({
                'success': True,
                'authenticated': True,
                'email': user.email,
                'name': user.name,
                'picture': user.picture_url,
                'tokens': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                }
            })

        except ValueError as e:
            logger.error(f"Invalid Google token: {e}")
            return Response(
                {'error': 'Invalid Google token'},
                status=401
            )
        except Exception as e:
            logger.error(f"Google login error: {e}")
            return Response(
                {'error': 'Authentication failed. Please try again.'},
                status=500
            )
```

**Why `authentication_classes = [JWTAuthentication]`?**

DRF's default `SessionAuthentication` enforces CSRF on all non-safe requests (POST, PUT, DELETE). Since this is a public endpoint (`AllowAny`) that receives unauthenticated requests, there's no CSRF token to validate. By explicitly setting `authentication_classes = [JWTAuthentication]`, we exclude `SessionAuthentication` and its CSRF enforcement. Without this, the endpoint returns HTTP 403 Forbidden with "CSRF Failed" for every request. See [Lesson #5](#8-lessons-learned--pitfalls).

### 3.6 URL Routing

**File**: `trading_api/urls/auth.py`

```python
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

    # Google OAuth - frontend-driven flow (PRIMARY)
    path('google/token', GoogleLoginCallbackView.as_view(), name='google-token-callback'),

    # Google OAuth - allauth redirect flow (LEGACY FALLBACK)
    path('google/callback', GoogleCallbackView.as_view(), name='google-callback'),
    path('google', RedirectView.as_view(url='/accounts/google/login/', permanent=False), name='google-login'),
]
```

**File**: `backend/urls.py` (main URL config)

```python
urlpatterns = [
    path('auth/', include('trading_api.urls.auth')),
    path('accounts/', include('allauth.urls')),  # Required for allauth fallback
    # ... other urls
]
```

### 3.7 Allauth Adapters

**File**: `trading_api/adapters.py`

Custom adapters handle the allauth redirect flow (legacy fallback) and account linking.

```python
import logging
from django.conf import settings
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.adapter import DefaultAccountAdapter
from rest_framework_simplejwt.tokens import RefreshToken
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class CustomAccountAdapter(DefaultAccountAdapter):
    """Redirect to frontend with JWT tokens after allauth OAuth login."""

    def get_login_redirect_url(self, request):
        user = request.user
        if user.is_authenticated:
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            tokens = {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }

            # Redirect to frontend with tokens as URL params
            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
            base_url = f"{frontend_url.rstrip('/')}/auth/callback"

            params = {
                'access': tokens['access'],
                'refresh': tokens['refresh'],
                'email': user.email,
                'name': getattr(user, 'name', '') or user.email.split('@')[0],
            }
            if hasattr(user, 'picture_url') and user.picture_url:
                params['picture'] = user.picture_url

            redirect_url = f"{base_url}?{urlencode(params)}"
            logger.info(f"OAuth login success, redirecting: {user.email}")
            return redirect_url

        return super().get_login_redirect_url(request)


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Handle Google account linking and user creation."""

    def pre_social_login(self, request, sociallogin):
        """Link Google account to existing user if email matches."""
        if sociallogin.is_existing:
            return

        email = sociallogin.user.email
        if not email:
            return

        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            existing_user = User.objects.get(email=email.lower())
            sociallogin.connect(request, existing_user)
            logger.info(f"Connected Google account to existing user: {email}")
        except User.DoesNotExist:
            logger.info(f"No existing user for {email}, proceeding to signup.")
        except Exception as e:
            logger.error(f"Error in pre_social_login: {e}", exc_info=True)

    def save_user(self, request, sociallogin, form=None):
        """Save new user with Google profile data."""
        user = super().save_user(request, sociallogin, form)

        extra_data = sociallogin.account.extra_data
        if not user.name and extra_data.get('name'):
            user.name = extra_data.get('name', '')
        if not user.picture_url and extra_data.get('picture'):
            user.picture_url = extra_data.get('picture', '')

        user.auth_provider = 'google'
        user.email_verified = True
        user.save()

        logger.info(f"Created new user from Google OAuth: {user.email}")
        return user

    def authentication_error(self, request, provider_id, error=None, exception=None, extra_context=None):
        """Log OAuth errors for debugging."""
        logger.error(f"Social Auth Error! Provider: {provider_id}, Error: {error}")
        if extra_context:
            logger.error(f"Extra Context: {extra_context}")
```

### 3.8 Google OAuth Setup Script

**File**: `scripts/setup_google_oauth.py`

This script runs at container startup to create the `SocialApp` database entry that allauth requires.

```python
#!/usr/bin/env python
"""
Setup Google OAuth for allauth.
Creates/updates SocialApp in database and links to Site.
Required for allauth to work - settings-based APP config alone is NOT sufficient.
"""

import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings.production')
django.setup()

from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp


def setup_google_oauth():
    """Configure Google OAuth with database SocialApp linked to Site."""

    # 1. Get all allowed hosts from environment
    allowed_hosts = os.environ.get('ALLOWED_HOSTS', '').split(',')
    valid_hosts = [h.strip() for h in allowed_hosts if h.strip() and h.strip() != '*']

    if not valid_hosts:
        valid_hosts = ['example.com']

    # 2. Create/Update Sites for each valid host
    sites = []
    for domain in valid_hosts:
        site, created = Site.objects.get_or_create(
            domain=domain,
            defaults={'name': 'Alpaca Trading SaaS'}
        )
        sites.append(site)

    # 3. Get OAuth credentials from environment
    client_id = os.environ.get('GOOGLE_CLIENT_ID', '')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET', '')

    if not client_id or not client_secret:
        print("Warning: GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET not set")
        return True

    # 4. Create or update SocialApp for Google
    app, created = SocialApp.objects.update_or_create(
        provider='google',
        defaults={
            'name': 'Google Auth',
            'client_id': client_id,
            'secret': client_secret,
        }
    )

    # 5. Link SocialApp to all Sites
    for site in sites:
        app.sites.add(site)

    return True


if __name__ == '__main__':
    setup_google_oauth()
```

### 3.9 Entrypoint Script

**File**: `entrypoint.sh`

The entrypoint runs database migrations, creates the Django Site entry, sets up Google OAuth, and starts Gunicorn.

```bash
#!/bin/bash
set -e

echo "Starting Backend..."

# Wait for database
sleep 3

# Run migrations
python manage.py migrate --noinput || {
    # Fallback: run migrations individually
    python manage.py migrate contenttypes --noinput || true
    python manage.py migrate auth --noinput || true
    python manage.py migrate sites --noinput || true
    python manage.py migrate sessions --noinput || true
    python manage.py migrate trading_api --noinput || true
    python manage.py migrate account --noinput || true
    python manage.py migrate socialaccount --noinput || true
    python manage.py migrate token_blacklist --noinput || true
}

# Create Django Site entry (required by allauth)
# Priority: SITE_DOMAIN env var > domain from FRONTEND_URL > first ALLOWED_HOST
python manage.py shell -c "
from django.contrib.sites.models import Site
import os
domain = os.environ.get('SITE_DOMAIN', '')
if not domain:
    frontend_url = os.environ.get('FRONTEND_URL', '')
    if frontend_url:
        domain = frontend_url.replace('https://', '').replace('http://', '').split('/')[0]
if not domain:
    domain = os.environ.get('ALLOWED_HOSTS', 'localhost').split(',')[0].strip()
site, created = Site.objects.get_or_create(id=1, defaults={'domain': domain, 'name': 'Alpaca Trading SaaS'})
if not created and domain and site.domain != domain:
    site.domain = domain
    site.save()
print(f'Site configured: {site.domain}')
" || echo "Site setup skipped"

# Setup Google OAuth in database (if credentials are set)
if [ -n "$GOOGLE_CLIENT_ID" ]; then
    python scripts/setup_google_oauth.py || echo "OAuth setup skipped"
fi

# Collect static files
python manage.py collectstatic --noinput --clear 2>/dev/null || python manage.py collectstatic --noinput

# Start Gunicorn
exec gunicorn backend.wsgi:application \
    --bind 0.0.0.0:${PORT:-8080} \
    --workers ${GUNICORN_WORKERS:-2} \
    --threads ${GUNICORN_THREADS:-4} \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --access-logfile - \
    --error-logfile -
```

---

## 4. Frontend Setup (React)

### 4.1 npm Dependencies

**File**: `dashboard/package.json`

```json
{
  "dependencies": {
    "@react-oauth/google": "^0.13.4",
    "axios": "^1.13.2",
    "react": "^19.2.0",
    "react-dom": "^19.2.0"
  }
}
```

Install:
```bash
npm install @react-oauth/google
```

`@react-oauth/google` is a React wrapper for Google Identity Services. It provides the `GoogleOAuthProvider` context and `GoogleLogin` button component, handling the popup flow and returning the Google ID token.

### 4.2 GoogleOAuthProvider Wrapper

**File**: `dashboard/src/main.jsx`

The entire app must be wrapped with `GoogleOAuthProvider` to load the Google Identity Services script and make the Client ID available to all components.

```jsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { GoogleOAuthProvider } from '@react-oauth/google'
import './index.css'
import App from './App.jsx'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID || ''}>
      <App />
    </GoogleOAuthProvider>
  </StrictMode>,
)
```

**Key points**:
- `VITE_GOOGLE_CLIENT_ID` is a Vite build-time environment variable (prefix `VITE_` is required)
- If the Client ID is empty/undefined, the GoogleLogin component won't render (handled by conditional check in the auth page)
- The `clientId` prop initializes the Google Identity Services library

### 4.3 API Module - Token Management

**File**: `dashboard/src/api.js`

The API module handles JWT token storage, axios interceptors for automatic Bearer token injection, and the Google login API call.

```javascript
import axios from 'axios';

// Backend API base URL (set at build time via Vite)
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// JWT Token Management
export const getAccessToken = () => localStorage.getItem('access_token');
export const getRefreshToken = () => localStorage.getItem('refresh_token');
export const setTokens = (access, refresh) => {
    if (access) localStorage.setItem('access_token', access);
    if (refresh) localStorage.setItem('refresh_token', refresh);
};
export const clearTokens = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
};

// Axios instance with base URL and credentials
const api = axios.create({
    baseURL: API_BASE,
    timeout: 10000,
    withCredentials: true,  // Send cookies with requests
});

// Request interceptor: add JWT Bearer token to all requests
api.interceptors.request.use((config) => {
    const token = getAccessToken();
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// Response interceptor: clear tokens on 401 (expired/invalid)
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            // Don't clear tokens for /auth/me check (expected 401 when not logged in)
            if (!error.config?.url?.includes('/auth/me')) {
                clearTokens();
            }
        }
        return Promise.reject(error);
    }
);

// Google Token Login - sends Google ID token to backend for verification
export const googleTokenLogin = async (idToken) => {
    const response = await api.post('/auth/google/token', { token: idToken });
    if (response.data.tokens) {
        setTokens(response.data.tokens.access, response.data.tokens.refresh);
    }
    return response.data;
};

// Check current auth status
export const getCurrentUser = async () => {
    try {
        const response = await api.get('/auth/me');
        return response.data;
    } catch (error) {
        if (error.response?.status === 401) {
            return { authenticated: false };
        }
        throw error;
    }
};

// Legacy: direct link to allauth Google login (fallback)
export const getLoginUrl = () => `${API_BASE}/auth/google`;

export default api;
```

### 4.4 GoogleLogin Component

**File**: `dashboard/src/App.jsx` (AuthPage component)

The AuthPage component uses `@react-oauth/google`'s `GoogleLogin` component for the popup flow, with a fallback to the legacy allauth redirect link if `VITE_GOOGLE_CLIENT_ID` is not set.

```jsx
import { GoogleLogin } from '@react-oauth/google';
import { googleTokenLogin, getLoginUrl, login, register } from './api';

function AuthPage({ onAuthSuccess }) {
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Handle successful Google login
  const handleGoogleSuccess = async (credentialResponse) => {
    setError('');
    setLoading(true);
    try {
      // credentialResponse.credential is the Google ID token
      const result = await googleTokenLogin(credentialResponse.credential);
      if (result.authenticated) {
        onAuthSuccess(result);
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Google sign-in failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Handle Google login failure/cancellation
  const handleGoogleError = () => {
    setError('Google sign-in was cancelled or failed. Please try again.');
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <h1>Your App Name</h1>

        {error && <div className="auth-error">{error}</div>}

        {/* Email/password form here... */}

        <div className="auth-divider"><span>or continue with</span></div>

        {/* Google Login - conditional on Client ID being available */}
        {import.meta.env.VITE_GOOGLE_CLIENT_ID ? (
          <div className="google-login-wrapper">
            <GoogleLogin
              onSuccess={handleGoogleSuccess}
              onError={handleGoogleError}
              theme="filled_black"      // Dark theme button
              size="large"              // Large button
              width="100%"              // Full width
              text="signin_with"        // "Sign in with Google" text
              shape="rectangular"       // Rectangular shape
            />
          </div>
        ) : (
          // Fallback: link to allauth redirect flow
          <a href={getLoginUrl()} className="btn-google-login">
            Sign in with Google
          </a>
        )}
      </div>
    </div>
  );
}
```

**GoogleLogin component props**:
- `onSuccess(credentialResponse)`: Called with `{ credential: "Google ID token JWT" }` after successful popup login
- `onError()`: Called when the popup is cancelled or fails
- `theme`: `"outline"` (light), `"filled_blue"`, or `"filled_black"`
- `size`: `"small"`, `"medium"`, or `"large"`
- `text`: `"signin_with"`, `"signup_with"`, `"continue_with"`, or `"signin"`
- `shape`: `"rectangular"`, `"pill"`, `"circle"`, or `"square"`
- `width`: CSS width value

### 4.5 CSS Styling

**File**: `dashboard/src/index.css`

```css
/* Center the Google login button */
.google-login-wrapper {
  display: flex;
  justify-content: center;
  width: 100%;
}

/* Divider between email form and Google login */
.auth-divider {
  display: flex;
  align-items: center;
  margin: 1.5rem 0;
  gap: 1rem;
}
.auth-divider::before,
.auth-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: rgba(255, 255, 255, 0.15);
}
.auth-divider span {
  font-size: 0.85rem;
  color: rgba(255, 255, 255, 0.5);
}
```

---

## 5. Infrastructure & Deployment

### 5.1 Frontend Dockerfile

**File**: `dashboard/Dockerfile`

```dockerfile
# Build stage
FROM node:20-alpine AS build
WORKDIR /app

COPY package*.json ./
RUN npm install
COPY . .

# Vite build-time environment variables
# These are EMBEDDED into the JS bundle at build time (not runtime)
ARG VITE_API_URL=https://api.stg.alpaca.samaanai.com
ENV VITE_API_URL=$VITE_API_URL

ARG VITE_GOOGLE_CLIENT_ID
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID

RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
```

**Critical**: Vite environment variables (`VITE_*`) are embedded at **build time**, not runtime. The `ARG` + `ENV` pattern passes the value from Docker build args into the Vite build process.

### 5.2 Nginx Configuration

**File**: `dashboard/nginx.conf`

```nginx
server {
    listen 8080;
    server_name localhost;

    root /usr/share/nginx/html;
    index index.html;

    # CRITICAL: index.html must NEVER be cached
    # Without this, browsers serve stale HTML after deployments,
    # referencing old JS/CSS hashes that no longer exist
    location = /index.html {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
        add_header Expires "0";
    }

    # SPA routing - serve index.html for all unmatched routes
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Aggressive caching for hashed static assets
    # Vite generates unique content hashes (e.g., index-tH2Uwuud.css)
    # so "immutable" is safe - different content = different filename
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Health check
    location /health {
        return 200 'OK';
        add_header Content-Type text/plain;
    }

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
}
```

### 5.3 Backend Dockerfile

**File**: `Dockerfile` (project root)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Collect static files at build time (uses SQLite fallback)
ENV DJANGO_SETTINGS_MODULE=backend.settings.production
RUN python manage.py collectstatic --noinput 2>/dev/null || true

EXPOSE 8080

ENTRYPOINT ["./entrypoint.sh"]
```

### 5.4 Docker Compose (Local Dev)

**File**: `docker-compose.yml`

```yaml
services:
  backend:
    build: .
    ports:
      - "8000:8080"
    environment:
      - DJANGO_SETTINGS_MODULE=backend.settings.base
      - DEBUG=true
      - FRONTEND_URL=http://localhost:5173
      - CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
      - ALLOWED_HOSTS=localhost,127.0.0.1
      - GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID:-}
      - GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET:-}

  frontend:
    build: ./dashboard
    ports:
      - "5173:8080"
    environment:
      - VITE_API_URL=http://localhost:8000
      - VITE_GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID:-}
    depends_on:
      - backend
```

For local dev, create a `.env` file:
```
GOOGLE_CLIENT_ID=your-client-id-here
GOOGLE_CLIENT_SECRET=your-client-secret-here
```

### 5.5 CI/CD - GitHub Actions

**File**: `.github/workflows/deploy-staging.yml`

Key sections for Google OAuth:

```yaml
# Backend deployment
- name: Deploy to Cloud Run
  uses: google-github-actions/deploy-cloudrun@v2
  with:
    service: ${{ env.BACKEND_SERVICE }}
    region: ${{ env.GCP_REGION }}
    image: gcr.io/${{ env.GCP_PROJECT }}/${{ env.BACKEND_SERVICE }}:${{ github.sha }}
    env_vars: |
      DJANGO_SETTINGS_MODULE=backend.settings.production
      GOOGLE_CLIENT_ID=${{ secrets.GOOGLE_CLIENT_ID }}
      GOOGLE_CLIENT_SECRET=${{ secrets.GOOGLE_CLIENT_SECRET }}
      ALLOWED_HOSTS=api.stg.alpaca.samaanai.com
      FRONTEND_URL=https://stg.alpaca.samaanai.com
      SESSION_COOKIE_DOMAIN=.stg.alpaca.samaanai.com
      CSRF_COOKIE_DOMAIN=.stg.alpaca.samaanai.com

# Frontend deployment
- name: Build and Push Docker image
  working-directory: dashboard
  run: |
    docker build \
      --build-arg VITE_API_URL=https://api.stg.alpaca.samaanai.com \
      --build-arg VITE_GOOGLE_CLIENT_ID=${{ secrets.GOOGLE_CLIENT_ID }} \
      -t gcr.io/$GCP_PROJECT/$FRONTEND_SERVICE:${{ github.sha }} .
```

**IMPORTANT**: The `deploy-cloudrun` action's `env_vars` format splits comma-separated values into separate environment variable names. Never use commas in values. See [Lesson #3](#8-lessons-learned--pitfalls).

---

## 6. Environment Variables Reference

### Backend Environment Variables

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `GOOGLE_CLIENT_ID` | Yes | `123456789-abc.apps.googleusercontent.com` | Google OAuth Client ID |
| `GOOGLE_CLIENT_SECRET` | Yes | `GOCSPX-abcdef123456` | Google OAuth Client Secret |
| `DJANGO_SECRET_KEY` | Yes | `django-insecure-...` | Django secret key for JWT signing |
| `FRONTEND_URL` | Yes | `https://stg.alpaca.samaanai.com` | Frontend URL for CORS and redirects |
| `ALLOWED_HOSTS` | Yes | `api.stg.alpaca.samaanai.com` | Django allowed hosts |
| `SESSION_COOKIE_DOMAIN` | Staging | `.stg.alpaca.samaanai.com` | Cookie domain (must cover both API and frontend subdomains) |
| `CSRF_COOKIE_DOMAIN` | Staging | `.stg.alpaca.samaanai.com` | CSRF cookie domain |
| `DJANGO_SETTINGS_MODULE` | Yes | `backend.settings.production` | Django settings module path |

### Frontend Environment Variables (Build-Time)

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `VITE_GOOGLE_CLIENT_ID` | Yes | `123456789-abc.apps.googleusercontent.com` | Same as backend's `GOOGLE_CLIENT_ID` |
| `VITE_API_URL` | Yes | `https://api.stg.alpaca.samaanai.com` | Backend API base URL |

### Local Development (`.env` file)

```env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-secret
VITE_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
VITE_API_URL=http://localhost:8000
```

---

## 7. Data Flow - Step by Step

### Complete Login Flow

```
1. USER clicks "Sign in with Google" button
   ↓
2. @react-oauth/google opens Google popup window
   - URL: https://accounts.google.com/o/oauth2/v2/auth
   - Params: client_id, redirect_uri (postmessage), scope (email, profile)
   ↓
3. USER authenticates with Google (enters email/password or picks account)
   ↓
4. Google returns ID token to popup via postMessage
   - Token is a JWT signed by Google containing: email, name, picture, sub (Google ID)
   ↓
5. @react-oauth/google calls onSuccess({ credential: "eyJ..." })
   ↓
6. handleGoogleSuccess() calls googleTokenLogin(credential)
   ↓
7. axios POST https://api.example.com/auth/google/token
   Body: { "token": "eyJ..." }
   ↓
8. Backend GoogleLoginCallbackView.post() receives token
   ↓
9. google.oauth2.id_token.verify_oauth2_token() validates:
   - Signature (against Google's public keys at https://www.googleapis.com/oauth2/v3/certs)
   - Expiry (tokens are valid for ~1 hour)
   - Audience (aud == GOOGLE_CLIENT_ID)
   ↓
10. Extract email, name, picture, sub from verified token
    ↓
11. User.objects.get_or_create(email=email)
    - New user: create with google_id, auth_provider='google', email_verified=True
    - Existing user: update google_id, auth_provider='both' (if was 'local')
    ↓
12. RefreshToken.for_user(user) generates JWT tokens:
    - Access token: valid 24 hours, used for API calls
    - Refresh token: valid 7 days, used to get new access token
    ↓
13. Backend returns:
    { authenticated: true, email, name, picture, tokens: { access, refresh } }
    ↓
14. Frontend setTokens(access, refresh) saves to localStorage
    ↓
15. onAuthSuccess(result) updates React state → dashboard renders
    ↓
16. All subsequent API calls include:
    Authorization: Bearer <access_token>
    (injected by axios request interceptor)
```

### Token Refresh Flow

```
1. Access token expires (after 24 hours)
   ↓
2. API returns 401 Unauthorized
   ↓
3. axios response interceptor catches 401
   - Clears tokens from localStorage (except for /auth/me calls)
   ↓
4. App detects user is no longer authenticated
   ↓
5. User must sign in again (with Google or email/password)
```

---

## 8. Lessons Learned & Pitfalls

### Lesson 1: Cross-Domain Session Cookie Loss

**Problem**: When using allauth's server-side redirect flow on Cloud Run, the session cookie set at `api.example.com` during OAuth initiation is not sent back on the Google callback redirect. This is because:
- `SESSION_COOKIE_DOMAIN` must cover both the API and frontend subdomains
- `SameSite=None` is required for cross-site cookie sending
- Cloud Run URLs (`.run.app`) are on a different domain entirely

**Solution**: Switch to frontend-driven OAuth flow. The frontend handles the Google popup directly, receives the ID token, and sends it to the backend in a single POST request. No session cookies needed.

### Lesson 2: SocialApp MultipleObjectsReturned

**Problem**: If you put Google OAuth credentials in BOTH `SOCIALACCOUNT_PROVIDERS['google']['APP']` (settings) AND the `SocialApp` database model, allauth raises `MultipleObjectsReturned` because it finds two matching entries.

**Solution**: Store credentials ONLY in the database via `SocialApp`. The `SOCIALACCOUNT_PROVIDERS` dict should contain only scope and auth params:

```python
# CORRECT
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    }
}

# WRONG - causes MultipleObjectsReturned
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': '...',
            'secret': '...',
        },
        'SCOPE': ['profile', 'email'],
    }
}
```

### Lesson 3: deploy-cloudrun Comma Splitting

**Problem**: The `google-github-actions/deploy-cloudrun@v2` GitHub Action parses `env_vars` as newlines of `KEY=VALUE`. When a value contains commas, the action splits them into separate environment variable names:

```yaml
# This BREAKS:
env_vars: |
  ALLOWED_HOSTS=host1.example.com,host2.example.com
  # Results in: ALLOWED_HOSTS=host1.example.com and host2.example.com=(empty)
```

**Solution**: Use single values in `env_vars` and hardcode the full list in Django settings:

```yaml
# This WORKS:
env_vars: |
  ALLOWED_HOSTS=api.example.com
```

```python
# In production.py, hardcode all known domains:
CLOUD_RUN_HOSTS = [
    'example.com',
    'api.example.com',
    '.run.app',
]
```

### Lesson 4: ALLOWED_HOSTS Validation

**Problem**: If your custom domain is not in `ALLOWED_HOSTS`, Django returns HTTP 400 "Invalid HTTP_HOST header" for **every single request**. This is a security feature that prevents HTTP Host header attacks.

**Solution**: Always hardcode your known production and staging domains in `production.py`. Don't rely solely on environment variables.

### Lesson 5: CSRF on AllowAny Views

**Problem**: DRF's default `SessionAuthentication` enforces CSRF validation on all non-safe HTTP methods (POST, PUT, DELETE), even on views with `permission_classes = [AllowAny]`. This means unauthenticated POST requests to `/auth/google/token` fail with HTTP 403 "CSRF Failed".

**Why it happens**: When a request includes a session cookie (which it does if `withCredentials: true` on the frontend), DRF's `SessionAuthentication` kicks in and validates the CSRF token. Since there's no CSRF token in an API POST request from a different domain, it fails.

**Solution**: Explicitly set `authentication_classes = [JWTAuthentication]` on all public auth views. This excludes `SessionAuthentication` and its CSRF enforcement:

```python
class GoogleLoginCallbackView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [JWTAuthentication]  # Excludes SessionAuthentication
```

### Lesson 6: Vite Build-Time Variables

**Problem**: Vite replaces `import.meta.env.VITE_*` at build time with literal values. If you set these variables at container runtime, they won't take effect - the old build-time values are already baked into the JavaScript bundle.

**Solution**: Pass `VITE_*` variables as Docker build args (`ARG` + `ENV`), not as runtime environment variables:

```dockerfile
ARG VITE_GOOGLE_CLIENT_ID
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID
RUN npm run build  # This is when VITE_ vars get embedded
```

### Lesson 7: Site Domain Configuration

**Problem**: allauth uses `SITE_ID = 1` to look up the Django `Site` object, which determines which `SocialApp` credentials to use. If Site ID=1 has the wrong domain (e.g., a Cloud Run URL instead of your custom domain), OAuth may fail.

**Solution**: In your entrypoint script, create/update Site ID=1 with the correct domain, preferring `FRONTEND_URL` domain over `ALLOWED_HOSTS`:

```python
domain = os.environ.get('SITE_DOMAIN', '')
if not domain:
    frontend_url = os.environ.get('FRONTEND_URL', '')
    if frontend_url:
        domain = frontend_url.replace('https://', '').replace('http://', '')
```

### Lesson 8: Nginx Cache Busting for SPAs

**Problem**: After deploying a new build, users see a broken/"scattered" UI because their browser serves the cached `index.html` which references old JS/CSS file hashes that no longer exist on the server.

**Solution**: Never cache `index.html`. Cache only hashed static assets:

```nginx
location = /index.html {
    add_header Cache-Control "no-cache, no-store, must-revalidate";
}

location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

---

## Quick Start Checklist

For a new project, follow these steps in order:

- [ ] Create Google Cloud OAuth credentials (consent screen + client ID)
- [ ] Add `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` to your secrets
- [ ] Install Python deps: `django-allauth`, `google-auth`, `djangorestframework-simplejwt`
- [ ] Install npm dep: `@react-oauth/google`
- [ ] Add allauth apps to `INSTALLED_APPS` and middleware
- [ ] Configure `SOCIALACCOUNT_PROVIDERS` (scope only, NO APP credentials)
- [ ] Add Google OAuth fields to User model (`google_id`, `auth_provider`, `picture_url`, `email_verified`)
- [ ] Create `GoogleLoginCallbackView` with token verification logic
- [ ] Add URL route: `path('google/token', GoogleLoginCallbackView.as_view())`
- [ ] Create OAuth setup script for database `SocialApp` creation
- [ ] Add script to entrypoint (runs at container startup)
- [ ] Wrap React app with `GoogleOAuthProvider`
- [ ] Add `googleTokenLogin()` to API module
- [ ] Add `GoogleLogin` component to auth page
- [ ] Add `VITE_GOOGLE_CLIENT_ID` to Dockerfile build args
- [ ] Add `GOOGLE_CLIENT_ID` to CI/CD env vars and `VITE_GOOGLE_CLIENT_ID` to build args
- [ ] Configure nginx to never cache `index.html`
- [ ] Set `authentication_classes = [JWTAuthentication]` on all public auth endpoints
- [ ] Test: click Google button -> popup -> authenticate -> dashboard loads
