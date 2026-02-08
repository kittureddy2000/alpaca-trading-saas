"""Trade model for storing trade history."""

from django.db import models
from django.conf import settings


class Trade(models.Model):
    """
    Store trade history for each user.
    Synced from Alpaca API and persisted locally.
    """

    ACTION_CHOICES = [
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('filled', 'Filled'),
        ('partially_filled', 'Partially Filled'),
        ('canceled', 'Canceled'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='trades',
        null=True,
        blank=True
    )

    # Order identification
    order_id = models.CharField(max_length=100, unique=True)
    client_order_id = models.CharField(max_length=100, blank=True)

    # Trade details
    symbol = models.CharField(max_length=10)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    quantity = models.IntegerField()
    order_type = models.CharField(max_length=20, default='market')

    # Pricing
    limit_price = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    stop_price = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    filled_avg_price = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)

    # Execution
    filled_qty = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # AI Analysis
    confidence = models.FloatField(null=True, blank=True)
    reasoning = models.TextField(blank=True)
    strategy = models.CharField(max_length=50, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    filled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'trades'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['symbol']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.action} {self.quantity} {self.symbol} @ {self.filled_avg_price or 'pending'}"

    @property
    def is_filled(self):
        return self.status == 'filled'

    @property
    def total_value(self):
        if self.filled_avg_price and self.filled_qty:
            return float(self.filled_avg_price) * self.filled_qty
        return None
