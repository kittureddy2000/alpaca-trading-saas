"""
Subscription model for Stripe billing integration.
Manages subscription tiers and feature access.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone


class UserSubscription(models.Model):
    """
    User subscription for SaaS billing.

    Tiers:
    - free: Paper trading, limited features
    - pro: Live trading, all indicators, custom settings
    - enterprise: API access, team features, priority support
    """

    TIER_CHOICES = [
        ('free', 'Free'),
        ('pro', 'Pro'),
        ('enterprise', 'Enterprise'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('canceled', 'Canceled'),
        ('trialing', 'Trialing'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscription'
    )

    # Subscription tier
    tier = models.CharField(
        max_length=20,
        choices=TIER_CHOICES,
        default='free'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )

    # Stripe Integration
    stripe_customer_id = models.CharField(max_length=255, blank=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True)
    stripe_price_id = models.CharField(max_length=255, blank=True)

    # Billing cycle
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)

    # Trial
    trial_start = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_subscriptions'
        verbose_name = 'User Subscription'
        verbose_name_plural = 'User Subscriptions'

    def __str__(self):
        return f"{self.user.email} - {self.tier}"

    @property
    def is_active(self):
        """Check if subscription is currently active."""
        return self.status in ['active', 'trialing']

    @property
    def is_trialing(self):
        """Check if user is in trial period."""
        if self.trial_end:
            return timezone.now() < self.trial_end
        return False

    @property
    def days_until_renewal(self):
        """Days until subscription renews."""
        if self.current_period_end:
            delta = self.current_period_end - timezone.now()
            return max(0, delta.days)
        return None

    # Feature Flags based on tier
    @property
    def max_watchlist_size(self):
        """Maximum watchlist size for this tier."""
        limits = settings.SUBSCRIPTION_TIERS.get(self.tier, {})
        return limits.get('max_watchlist_size', 5)

    @property
    def live_trading_enabled(self):
        """Whether live trading is enabled for this tier."""
        limits = settings.SUBSCRIPTION_TIERS.get(self.tier, {})
        return limits.get('live_trading_enabled', False)

    @property
    def api_access_enabled(self):
        """Whether API access is enabled for this tier."""
        limits = settings.SUBSCRIPTION_TIERS.get(self.tier, {})
        return limits.get('api_access_enabled', False)

    @property
    def advanced_indicators(self):
        """Whether advanced indicators are enabled."""
        limits = settings.SUBSCRIPTION_TIERS.get(self.tier, {})
        return limits.get('advanced_indicators', False)

    @property
    def collar_calculator(self):
        """Whether collar calculator is enabled."""
        limits = settings.SUBSCRIPTION_TIERS.get(self.tier, {})
        return limits.get('collar_calculator', False)

    @property
    def custom_settings(self):
        """Whether custom settings are enabled."""
        limits = settings.SUBSCRIPTION_TIERS.get(self.tier, {})
        return limits.get('custom_settings', False)

    def get_features(self):
        """Get all features for this subscription tier."""
        return {
            'tier': self.tier,
            'status': self.status,
            'is_active': self.is_active,
            'max_watchlist_size': self.max_watchlist_size,
            'live_trading_enabled': self.live_trading_enabled,
            'api_access_enabled': self.api_access_enabled,
            'advanced_indicators': self.advanced_indicators,
            'collar_calculator': self.collar_calculator,
            'custom_settings': self.custom_settings,
            'current_period_end': self.current_period_end,
            'cancel_at_period_end': self.cancel_at_period_end,
        }

    @classmethod
    def get_or_create_for_user(cls, user):
        """Get or create free subscription for a user."""
        subscription, created = cls.objects.get_or_create(
            user=user,
            defaults={'tier': 'free', 'status': 'active'}
        )
        return subscription
