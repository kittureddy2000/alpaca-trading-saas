"""
Custom User model with Alpaca integration fields.
Designed for multi-tenant SaaS with per-user broker connections.
"""

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.conf import settings
from cryptography.fernet import Fernet
import base64
import os


def get_encryption_key():
    """Get or generate encryption key for API secrets."""
    key = settings.ENCRYPTION_KEY
    if not key:
        # Generate a key if not set (for development)
        key = Fernet.generate_key().decode()
    # Ensure key is properly formatted
    if len(key) == 32:
        key = base64.urlsafe_b64encode(key.encode()).decode()
    return key.encode()


class UserManager(BaseUserManager):
    """Custom user manager for email-based authentication."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model with Alpaca trading integration.

    Features:
    - Email-based authentication
    - Google OAuth support
    - Per-user Alpaca API credentials (encrypted)
    - Subscription tier tracking
    """

    # Core fields
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100, blank=True)
    picture = models.URLField(max_length=500, blank=True)

    # Account status
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    # Google OAuth
    google_id = models.CharField(max_length=100, blank=True, null=True, unique=True)

    # Alpaca Connection (API Key approach)
    alpaca_api_key = models.CharField(max_length=50, blank=True)
    _alpaca_secret_key = models.BinaryField(null=True, blank=True, db_column='alpaca_secret_key')
    alpaca_account_id = models.CharField(max_length=50, blank=True)
    alpaca_is_paper = models.BooleanField(default=True)
    alpaca_connected = models.BooleanField(default=False)
    alpaca_connected_at = models.DateTimeField(null=True, blank=True)
    alpaca_last_error = models.TextField(blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.email

    @property
    def alpaca_secret_key(self):
        """Decrypt and return the Alpaca secret key."""
        if not self._alpaca_secret_key:
            return ''
        try:
            f = Fernet(get_encryption_key())
            return f.decrypt(bytes(self._alpaca_secret_key)).decode()
        except Exception:
            return ''

    @alpaca_secret_key.setter
    def alpaca_secret_key(self, value):
        """Encrypt and store the Alpaca secret key."""
        if not value:
            self._alpaca_secret_key = None
        else:
            f = Fernet(get_encryption_key())
            self._alpaca_secret_key = f.encrypt(value.encode())

    def get_alpaca_credentials(self):
        """Get Alpaca API credentials for this user."""
        if not self.alpaca_connected or not self.alpaca_api_key:
            return None
        return {
            'api_key': self.alpaca_api_key,
            'secret_key': self.alpaca_secret_key,
            'paper': self.alpaca_is_paper,
        }

    def mask_api_key(self):
        """Return masked API key for display (show last 4 chars)."""
        if not self.alpaca_api_key:
            return ''
        return f"{'*' * (len(self.alpaca_api_key) - 4)}{self.alpaca_api_key[-4:]}"

    @property
    def subscription_tier(self):
        """Get user's subscription tier."""
        try:
            return self.subscription.tier
        except UserSubscription.DoesNotExist:
            return 'free'

    @property
    def can_live_trade(self):
        """Check if user can do live trading based on subscription."""
        try:
            return self.subscription.live_trading_enabled
        except:
            return False


# Import here to avoid circular import
from .subscription import UserSubscription
