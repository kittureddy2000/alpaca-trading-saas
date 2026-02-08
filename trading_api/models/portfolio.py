"""Portfolio and Position snapshot models."""

from django.db import models
from django.conf import settings


class PortfolioSnapshot(models.Model):
    """
    Periodic snapshots of user's portfolio for tracking performance.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='portfolio_snapshots'
    )

    # Account values
    portfolio_value = models.DecimalField(max_digits=14, decimal_places=2)
    cash = models.DecimalField(max_digits=14, decimal_places=2)
    buying_power = models.DecimalField(max_digits=14, decimal_places=2)
    equity = models.DecimalField(max_digits=14, decimal_places=2)

    # Performance
    daily_change = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    daily_change_pct = models.DecimalField(max_digits=8, decimal_places=4, default=0)

    # Metadata
    timestamp = models.DateTimeField(auto_now_add=True)
    is_paper = models.BooleanField(default=True)

    class Meta:
        db_table = 'portfolio_snapshots'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.user.email} - ${self.portfolio_value} @ {self.timestamp}"


class PositionSnapshot(models.Model):
    """
    Snapshot of individual positions at a point in time.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='position_snapshots'
    )

    # Position details
    symbol = models.CharField(max_length=10)
    qty = models.IntegerField()
    avg_entry_price = models.DecimalField(max_digits=12, decimal_places=4)
    current_price = models.DecimalField(max_digits=12, decimal_places=4)
    market_value = models.DecimalField(max_digits=14, decimal_places=2)

    # P&L
    unrealized_pl = models.DecimalField(max_digits=14, decimal_places=2)
    unrealized_plpc = models.DecimalField(max_digits=8, decimal_places=4)
    cost_basis = models.DecimalField(max_digits=14, decimal_places=2)

    # Timestamp
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'position_snapshots'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['symbol']),
        ]

    def __str__(self):
        return f"{self.symbol}: {self.qty} @ {self.current_price}"
