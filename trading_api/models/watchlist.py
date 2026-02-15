"""Watchlist model for user stock tracking."""

from django.db import models
from django.conf import settings


class WatchlistItem(models.Model):
    """
    User's watchlist for tracking stocks.
    Each user has their own isolated watchlist.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='watchlist_items'
    )
    symbol = models.CharField(max_length=10)
    added_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'watchlist_items'
        unique_together = ('user', 'symbol')
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.user.email}: {self.symbol}"

    @classmethod
    def get_user_symbols(cls, user):
        """Get list of symbols in user's watchlist."""
        return list(cls.objects.filter(user=user).values_list('symbol', flat=True))

    @classmethod
    def seed_default_watchlist(cls, user, symbols=None):
        """Seed default watchlist for new users."""
        if symbols is None:
            symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']

        symbols = symbols[:500]  # Generous limit for all users

        for symbol in symbols:
            cls.objects.get_or_create(user=user, symbol=symbol)
