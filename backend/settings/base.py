"""
Django settings for Alpaca Trading SaaS.
Multi-tenant trading platform with Stripe billing.
"""

import os
from pathlib import Path
from datetime import timedelta

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'dev-secret-key-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

ALLOWED_HOSTS = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').replace(',', ' ').split()]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    # Third party
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',

    # Local
    'trading_api',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # MUST BE FIRST for OAuth preflight
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.contrib.sites.middleware.CurrentSiteMiddleware',  # Required for dynamic site selection
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'alpaca_trading'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

# Use SQLite for development if no PostgreSQL configured
if os.environ.get('USE_SQLITE', 'false').lower() == 'true':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Custom User Model
AUTH_USER_MODEL = 'trading_api.User'

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/New_York'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Sites framework (required for allauth)
SITE_ID = 1

# REST Framework
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
    'EXCEPTION_HANDLER': 'rest_framework.views.exception_handler',
}

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=24),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# CORS Settings
CORS_ALLOWED_ORIGINS = os.environ.get(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173'
).split(',')
CORS_ALLOW_CREDENTIALS = True

# Allauth settings
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_USER_MODEL_USERNAME_FIELD = None  # Custom user model has no username field
ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https'  # Always use HTTPS for OAuth callbacks

# Custom adapters for OAuth JWT redirect
ACCOUNT_ADAPTER = 'trading_api.adapters.CustomAccountAdapter'
SOCIALACCOUNT_ADAPTER = 'trading_api.adapters.CustomSocialAccountAdapter'

# Social account settings
SOCIALACCOUNT_STORE_TOKENS = True
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True  # Auto-link by email

# Login redirect URL
LOGIN_REDIRECT_URL = os.environ.get('LOGIN_REDIRECT_URL', '/auth/callback')

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        # APP credentials are stored in database via SocialApp model
        # Do NOT put APP here - it causes MultipleObjectsReturned when both
        # settings-based and database-based configs exist
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    }
}

# Frontend URL for redirects
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:5173')

# Alpaca API (default for paper trading demo & OAuth)
ALPACA_API_KEY = os.environ.get('ALPACA_API_KEY', '')
ALPACA_SECRET_KEY = os.environ.get('ALPACA_SECRET_KEY', '')
ALPACA_PAPER = os.environ.get('ALPACA_PAPER', 'true').lower() == 'true'

# Alpaca OAuth (SaaS Mode)
ALPACA_CLIENT_ID = os.environ.get('ALPACA_CLIENT_ID', '')
ALPACA_CLIENT_SECRET = os.environ.get('ALPACA_CLIENT_SECRET', '')
ALPACA_REDIRECT_URI = os.environ.get('ALPACA_REDIRECT_URI', '')

# Stripe Billing
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

# Stripe Price IDs (create these in Stripe Dashboard)
STRIPE_PRICE_ID_PRO = os.environ.get('STRIPE_PRICE_ID_PRO', '')
STRIPE_PRICE_ID_ENTERPRISE = os.environ.get('STRIPE_PRICE_ID_ENTERPRISE', '')

# Gemini AI
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

# Encryption key for storing API secrets
ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY', '')

# Trading Configuration (defaults for new users)
DEFAULT_TRADING_CONFIG = {
    'STRATEGY': 'balanced',
    'ANALYSIS_INTERVAL_MINUTES': 15,
    'MAX_POSITION_PCT': 0.10,
    'MAX_DAILY_LOSS_PCT': 0.03,
    'MIN_CONFIDENCE': 0.70,
    'STOP_LOSS_PCT': 0.05,
    'TAKE_PROFIT_PCT': 0.10,
}

# Subscription Tier Limits
SUBSCRIPTION_TIERS = {
    'free': {
        'max_watchlist_size': 500,
        'live_trading_enabled': True,
        'api_access_enabled': True,
        'advanced_indicators': True,
        'collar_calculator': True,
        'custom_settings': True,
    },
    'pro': {
        'max_watchlist_size': 100,
        'live_trading_enabled': True,
        'api_access_enabled': False,
        'advanced_indicators': True,
        'collar_calculator': True,
        'custom_settings': True,
    },
    'enterprise': {
        'max_watchlist_size': 500,
        'live_trading_enabled': True,
        'api_access_enabled': True,
        'advanced_indicators': True,
        'collar_calculator': True,
        'custom_settings': True,
    },
}

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'trading_api': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        # Add allauth logging to debug OAuth issues
        'allauth': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'allauth.socialaccount': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        # OAuth library logging for token exchange debugging
        'oauthlib': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'requests_oauthlib': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
