"""
Alpaca Trading Service.
Per-user Alpaca API client management for multi-tenant SaaS.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from zoneinfo import ZoneInfo

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderStatus, QueryOrderStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame

logger = logging.getLogger(__name__)


class AlpacaService:
    """
    Alpaca Trading Service for a specific user.

    Creates per-user Alpaca client connections.
    No shared state - each instance uses user's own credentials.
    """

    def __init__(self, api_key: str = None, secret_key: str = None, access_token: str = None, paper: bool = True):
        """
        Initialize Alpaca client for a user.

        Args:
            api_key: User's Alpaca API key (optional if using OAuth)
            secret_key: User's Alpaca secret key (optional if using OAuth)
            access_token: User's Alpaca OAuth access token
            paper: Whether to use paper trading (default True)
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.access_token = access_token
        self.paper = paper

        # Initialize trading client
        if access_token:
            self.trading_client = TradingClient(
                oauth_token=access_token,
                paper=paper
            )
            # Data client usually uses the same auth
            # Note: For strict typing, might need to check if SDK supports oauth_token param for DataClient
            # If not, we might need to pass it as api_key or use custom headers
            self.data_client = StockHistoricalDataClient(
                api_key=access_token, # SDK often treats token as key if no secret
                secret_key=''   
            )
        else:
            self.trading_client = TradingClient(
                api_key=api_key,
                secret_key=secret_key,
                paper=paper
            )
            self.data_client = StockHistoricalDataClient(
                api_key=api_key,
                secret_key=secret_key
            )

        logger.info(f"AlpacaService initialized (paper={paper}, oauth={bool(access_token)})")

    @classmethod
    def from_user(cls, user) -> Optional['AlpacaService']:
        """
        Create AlpacaService from a User model.

        Args:
            user: User model instance with Alpaca credentials

        Returns:
            AlpacaService instance or None if not connected
        """
        credentials = user.get_alpaca_credentials()
        if not credentials:
            return None

        return cls(
            api_key=credentials.get('api_key'),
            secret_key=credentials.get('secret_key'),
            access_token=credentials.get('access_token'),
            paper=credentials.get('paper', True)
        )

    def test_connection(self) -> Dict[str, Any]:
        """
        Test Alpaca API connection.

        Returns:
            Dict with connection status and account info
        """
        try:
            account = self.trading_client.get_account()
            return {
                'connected': True,
                'account_id': account.id,
                'account_number': account.account_number,
                'status': account.status,
                'paper': self.paper,
            }
        except Exception as e:
            logger.error(f"Alpaca connection test failed: {e}")
            return {
                'connected': False,
                'error': str(e),
            }

    def get_account(self) -> Dict[str, Any]:
        """Get account information."""
        try:
            account = self.trading_client.get_account()
            return {
                'id': account.id,
                'account_number': account.account_number,
                'status': account.status,
                'cash': float(account.cash),
                'buying_power': float(account.buying_power),
                'portfolio_value': float(account.portfolio_value),
                'equity': float(account.equity),
                'last_equity': float(account.last_equity),
                'currency': account.currency,
                'pattern_day_trader': account.pattern_day_trader,
                'trading_blocked': account.trading_blocked,
                'transfers_blocked': account.transfers_blocked,
                'account_blocked': account.account_blocked,
            }
        except Exception as e:
            logger.error(f"Failed to get account: {e}")
            raise

    def get_positions(self) -> List[Dict[str, Any]]:
        """Get all current positions."""
        try:
            positions = self.trading_client.get_all_positions()
            return [
                {
                    'symbol': pos.symbol,
                    'qty': int(pos.qty),
                    'avg_entry_price': float(pos.avg_entry_price),
                    'current_price': float(pos.current_price),
                    'market_value': float(pos.market_value),
                    'cost_basis': float(pos.cost_basis),
                    'unrealized_pl': float(pos.unrealized_pl),
                    'unrealized_plpc': float(pos.unrealized_plpc),
                    'side': pos.side,
                }
                for pos in positions
            ]
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []

    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get position for a specific symbol."""
        try:
            pos = self.trading_client.get_open_position(symbol)
            return {
                'symbol': pos.symbol,
                'qty': int(pos.qty),
                'avg_entry_price': float(pos.avg_entry_price),
                'current_price': float(pos.current_price),
                'market_value': float(pos.market_value),
                'cost_basis': float(pos.cost_basis),
                'unrealized_pl': float(pos.unrealized_pl),
                'unrealized_plpc': float(pos.unrealized_plpc),
            }
        except Exception as e:
            logger.debug(f"No position for {symbol}: {e}")
            return None

    def place_market_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        time_in_force: str = 'day'
    ) -> Dict[str, Any]:
        """
        Place a market order.

        Args:
            symbol: Stock symbol
            qty: Number of shares
            side: 'buy' or 'sell'
            time_in_force: Order duration ('day', 'gtc', 'ioc', 'fok')

        Returns:
            Order details
        """
        try:
            order_side = OrderSide.BUY if side.lower() == 'buy' else OrderSide.SELL
            tif = getattr(TimeInForce, time_in_force.upper(), TimeInForce.DAY)

            order_request = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=order_side,
                time_in_force=tif
            )

            order = self.trading_client.submit_order(order_request)

            logger.info(f"Placed market order: {side} {qty} {symbol}")

            return {
                'id': str(order.id),
                'client_order_id': order.client_order_id,
                'symbol': order.symbol,
                'qty': int(order.qty),
                'side': order.side.value,
                'type': order.type.value,
                'status': order.status.value,
                'created_at': order.created_at.isoformat() if order.created_at else None,
            }
        except Exception as e:
            logger.error(f"Failed to place market order: {e}")
            raise

    def place_limit_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        limit_price: float,
        time_in_force: str = 'day'
    ) -> Dict[str, Any]:
        """
        Place a limit order.

        Args:
            symbol: Stock symbol
            qty: Number of shares
            side: 'buy' or 'sell'
            limit_price: Limit price
            time_in_force: Order duration

        Returns:
            Order details
        """
        try:
            order_side = OrderSide.BUY if side.lower() == 'buy' else OrderSide.SELL
            tif = getattr(TimeInForce, time_in_force.upper(), TimeInForce.DAY)

            order_request = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=order_side,
                time_in_force=tif,
                limit_price=limit_price
            )

            order = self.trading_client.submit_order(order_request)

            logger.info(f"Placed limit order: {side} {qty} {symbol} @ {limit_price}")

            return {
                'id': str(order.id),
                'client_order_id': order.client_order_id,
                'symbol': order.symbol,
                'qty': int(order.qty),
                'side': order.side.value,
                'type': order.type.value,
                'limit_price': float(order.limit_price) if order.limit_price else None,
                'status': order.status.value,
                'created_at': order.created_at.isoformat() if order.created_at else None,
            }
        except Exception as e:
            logger.error(f"Failed to place limit order: {e}")
            raise

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get order by ID."""
        try:
            order = self.trading_client.get_order_by_id(order_id)
            return {
                'id': str(order.id),
                'symbol': order.symbol,
                'qty': int(order.qty),
                'filled_qty': int(order.filled_qty) if order.filled_qty else 0,
                'side': order.side.value,
                'type': order.type.value,
                'status': order.status.value,
                'limit_price': float(order.limit_price) if order.limit_price else None,
                'filled_avg_price': float(order.filled_avg_price) if order.filled_avg_price else None,
                'created_at': order.created_at.isoformat() if order.created_at else None,
                'filled_at': order.filled_at.isoformat() if order.filled_at else None,
            }
        except Exception as e:
            logger.error(f"Failed to get order {order_id}: {e}")
            return None

    def get_orders_history(self, limit: int = 100, status: str = 'all') -> List[Dict[str, Any]]:
        """
        Get order history.

        Args:
            limit: Maximum number of orders to return
            status: Filter by status ('all', 'open', 'closed')

        Returns:
            List of orders
        """
        try:
            # Map status to QueryOrderStatus
            if status == 'open':
                query_status = QueryOrderStatus.OPEN
            elif status == 'closed':
                query_status = QueryOrderStatus.CLOSED
            else:
                query_status = QueryOrderStatus.ALL

            request = GetOrdersRequest(
                status=query_status,
                limit=limit
            )

            orders = self.trading_client.get_orders(request)

            return [
                {
                    'id': str(order.id),
                    'symbol': order.symbol,
                    'qty': int(order.qty),
                    'filled_qty': int(order.filled_qty) if order.filled_qty else 0,
                    'side': order.side.value,
                    'type': order.type.value,
                    'status': order.status.value,
                    'limit_price': float(order.limit_price) if order.limit_price else None,
                    'filled_avg_price': float(order.filled_avg_price) if order.filled_avg_price else None,
                    'created_at': order.created_at.isoformat() if order.created_at else None,
                    'filled_at': order.filled_at.isoformat() if order.filled_at else None,
                }
                for order in orders
            ]
        except Exception as e:
            logger.error(f"Failed to get orders history: {e}")
            return []

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        try:
            self.trading_client.cancel_order_by_id(order_id)
            logger.info(f"Cancelled order {order_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    def is_market_open(self) -> bool:
        """Check if the market is currently open."""
        try:
            clock = self.trading_client.get_clock()
            return clock.is_open
        except Exception as e:
            logger.error(f"Failed to check market status: {e}")
            # Fallback to manual check
            return self._check_market_hours_fallback()

    def _check_market_hours_fallback(self) -> bool:
        """Fallback market hours check."""
        et = ZoneInfo('America/New_York')
        now = datetime.now(et)

        # Weekend check
        if now.weekday() >= 5:
            return False

        # Market hours: 9:30 AM - 4:00 PM ET
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)

        return market_open <= now < market_close

    def get_market_hours(self) -> Dict[str, Any]:
        """Get market hours for today."""
        try:
            clock = self.trading_client.get_clock()
            return {
                'is_open': clock.is_open,
                'next_open': clock.next_open.isoformat() if clock.next_open else None,
                'next_close': clock.next_close.isoformat() if clock.next_close else None,
            }
        except Exception as e:
            logger.error(f"Failed to get market hours: {e}")
            return {
                'is_open': self._check_market_hours_fallback(),
                'next_open': None,
                'next_close': None,
            }

    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get latest quote for a symbol."""
        try:
            request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            quotes = self.data_client.get_stock_latest_quote(request)

            if symbol in quotes:
                quote = quotes[symbol]
                return {
                    'symbol': symbol,
                    'bid_price': float(quote.bid_price),
                    'ask_price': float(quote.ask_price),
                    'bid_size': int(quote.bid_size),
                    'ask_size': int(quote.ask_size),
                    'timestamp': quote.timestamp.isoformat() if quote.timestamp else None,
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get quote for {symbol}: {e}")
            return None

    def get_bars(
        self,
        symbol: str,
        timeframe: str = '1Day',
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get historical bars for a symbol.

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe ('1Min', '5Min', '15Min', '1Hour', '1Day')
            limit: Number of bars

        Returns:
            List of OHLCV bars
        """
        try:
            tf = getattr(TimeFrame, timeframe, TimeFrame.Day)

            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=tf,
                limit=limit
            )

            bars = self.data_client.get_stock_bars(request)

            if symbol in bars:
                return [
                    {
                        'timestamp': bar.timestamp.isoformat(),
                        'open': float(bar.open),
                        'high': float(bar.high),
                        'low': float(bar.low),
                        'close': float(bar.close),
                        'volume': int(bar.volume),
                        'vwap': float(bar.vwap) if bar.vwap else None,
                    }
                    for bar in bars[symbol]
                ]
            return []
        except Exception as e:
            logger.error(f"Failed to get bars for {symbol}: {e}")
            return []

    def get_snapshot(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get snapshot for a symbol (latest trade, quote, and minute bar).

        Args:
            symbol: Stock symbol

        Returns:
            Snapshot data
        """
        try:
            from alpaca.data.requests import StockSnapshotRequest
            
            request = StockSnapshotRequest(symbol_or_symbols=symbol)
            snapshots = self.data_client.get_stock_snapshot(request)

            if symbol in snapshots:
                snap = snapshots[symbol]
                
                # Daily bar for change calculation
                daily_bar = snap.daily_bar
                prev_close = 0
                
                if snap.previous_daily_bar:
                    prev_close = float(snap.previous_daily_bar.close)
                elif daily_bar:
                    prev_close = float(daily_bar.open) # Approximation

                current_price = 0
                if snap.latest_trade:
                    current_price = float(snap.latest_trade.price)
                elif snap.latest_quote:
                    current_price = (float(snap.latest_quote.ask_price) + float(snap.latest_quote.bid_price)) / 2
                elif daily_bar:
                    current_price = float(daily_bar.close)

                change = current_price - prev_close
                change_pct = (change / prev_close * 100) if prev_close else 0

                return {
                    'symbol': symbol,
                    'price': current_price,
                    'change': change,
                    'change_pct': change_pct,
                    'volume': int(daily_bar.volume) if daily_bar else 0,
                    'prev_close': prev_close,
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get snapshot for {symbol}: {e}")
            return None
