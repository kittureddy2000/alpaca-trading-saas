"""
Per-user trading settings.
Allows each user to customize their trading parameters.
"""

from django.db import models
from django.conf import settings


class UserSettings(models.Model):
    """
    Per-user trading configuration.

    Each user can customize:
    - Trading strategy
    - Risk parameters
    - Analysis intervals
    - Notification preferences
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='settings'
    )

    # Trading Strategy
    STRATEGY_CHOICES = [
        ('momentum', 'Momentum'),
        ('mean_reversion', 'Mean Reversion'),
        ('contrarian', 'Contrarian'),
        ('balanced', 'Balanced'),
    ]
    strategy = models.CharField(
        max_length=20,
        choices=STRATEGY_CHOICES,
        default='balanced'
    )

    # Analysis Configuration
    analysis_interval_minutes = models.IntegerField(default=15)

    # Risk Management
    max_position_pct = models.FloatField(default=0.10)  # 10% max per position
    max_daily_loss_pct = models.FloatField(default=0.03)  # 3% max daily loss
    min_confidence = models.FloatField(default=0.70)  # 70% min confidence for trades
    stop_loss_pct = models.FloatField(default=0.05)  # 5% stop loss
    take_profit_pct = models.FloatField(default=0.10)  # 10% take profit

    # Notifications
    email_daily_summary = models.BooleanField(default=True)
    email_trade_alerts = models.BooleanField(default=True)
    email_weekly_report = models.BooleanField(default=False)

    # Indicators
    active_indicators = models.JSONField(default=dict)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Set default indicators if empty
        if not self.active_indicators:
            self.active_indicators = {
                'RSI': True,
                'MACD': True,
                'SMA': True,
                'EMA': True,
                'Bollinger Bands': True,
                'Volume Analysis': True,
                'VWAP': True,
                'ATR': True,
                'Price Changes': True,
            }
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'user_settings'
        verbose_name = 'User Settings'
        verbose_name_plural = 'User Settings'

    def __str__(self):
        return f"Settings for {self.user.email}"

    def to_config_dict(self):
        """Convert settings to config dictionary for trading engine."""
        return {
            'STRATEGY': self.strategy,
            'ANALYSIS_INTERVAL_MINUTES': self.analysis_interval_minutes,
            'MAX_POSITION_PCT': self.max_position_pct,
            'MAX_DAILY_LOSS_PCT': self.max_daily_loss_pct,
            'MIN_CONFIDENCE': self.min_confidence,
            'STOP_LOSS_PCT': self.stop_loss_pct,
            'TAKE_PROFIT_PCT': self.take_profit_pct,
        }

    @classmethod
    def get_or_create_for_user(cls, user):
        """Get or create settings for a user with defaults."""
        settings_obj, created = cls.objects.get_or_create(user=user)
        return settings_obj
