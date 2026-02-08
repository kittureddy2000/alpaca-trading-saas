"""API URL routes."""

from django.urls import path
from trading_api.views.api import (
    PortfolioView,
    PositionsView,
    TradesView,
    WatchlistView,
    MarketView,
    IndicatorsView,
    OptionChainView,
    CollarStrategyView,
)
from trading_api.views.alpaca import (
    AlpacaConnectView,
    AlpacaDisconnectView,
    AlpacaStatusView,
)
from trading_api.views.settings import (
    UserSettingsView,
)
from trading_api.views.billing import (
    SubscriptionView,
    CheckoutView,
    PortalView,
    WebhookView,
)

urlpatterns = [
    # Portfolio & Trading
    path('portfolio', PortfolioView.as_view(), name='portfolio'),
    path('positions', PositionsView.as_view(), name='positions'),
    path('trades', TradesView.as_view(), name='trades'),
    path('watchlist', WatchlistView.as_view(), name='watchlist'),
    path('market', MarketView.as_view(), name='market'),
    path('indicators', IndicatorsView.as_view(), name='indicators'),

    # Options
    path('option-chain', OptionChainView.as_view(), name='option-chain'),
    path('collar-strategy', CollarStrategyView.as_view(), name='collar-strategy'),

    # Alpaca Connection
    path('alpaca/connect', AlpacaConnectView.as_view(), name='alpaca-connect'),
    path('alpaca/disconnect', AlpacaDisconnectView.as_view(), name='alpaca-disconnect'),
    path('alpaca/status', AlpacaStatusView.as_view(), name='alpaca-status'),

    # User Settings
    path('settings', UserSettingsView.as_view(), name='user-settings'),

    # Billing
    path('subscription', SubscriptionView.as_view(), name='subscription'),
    path('subscription/checkout', CheckoutView.as_view(), name='checkout'),
    path('subscription/portal', PortalView.as_view(), name='portal'),
    path('subscription/webhook', WebhookView.as_view(), name='webhook'),
]
