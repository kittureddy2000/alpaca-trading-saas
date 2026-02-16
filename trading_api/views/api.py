"""Core API views for trading functionality."""

import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from trading_api.models import (
    Trade, PortfolioSnapshot, PositionSnapshot, WatchlistItem
)
from trading_api.services.alpaca_service import AlpacaService

import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)


class PortfolioView(APIView):
    """Get portfolio overview."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Try to get live data from Alpaca
        if user.alpaca_connected:
            try:
                service = AlpacaService.from_user(user)
                if service:
                    account = service.get_account()
                    positions = service.get_positions()

                    # Calculate daily change from last equity
                    equity = account.get('equity', 0)
                    last_equity = account.get('last_equity', equity)
                    daily_change = equity - last_equity
                    daily_change_pct = (daily_change / last_equity * 100) if last_equity else 0

                    # Save snapshot
                    self._save_snapshot(user, account, daily_change, daily_change_pct)

                    return Response({
                        'account': {
                            'portfolio_value': account.get('portfolio_value'),
                            'cash': account.get('cash'),
                            'buying_power': account.get('buying_power'),
                            'equity': account.get('equity'),
                        },
                        'positions': positions,
                        'performance': {
                            'daily_change': daily_change,
                            'daily_change_pct': daily_change_pct,
                        },
                        'source': 'alpaca_live',
                    })
            except Exception as e:
                logger.error(f"Failed to get portfolio from Alpaca: {e}")

        # Fallback to last snapshot
        try:
            snapshot = PortfolioSnapshot.objects.filter(user=user).first()
            if snapshot:
                positions = PositionSnapshot.objects.filter(
                    user=user,
                    timestamp__gte=snapshot.timestamp - timedelta(minutes=5)
                )
                return Response({
                    'account': {
                        'portfolio_value': float(snapshot.portfolio_value),
                        'cash': float(snapshot.cash),
                        'buying_power': float(snapshot.buying_power),
                        'equity': float(snapshot.equity),
                    },
                    'positions': [
                        {
                            'symbol': p.symbol,
                            'qty': p.qty,
                            'avg_entry_price': float(p.avg_entry_price),
                            'current_price': float(p.current_price),
                            'market_value': float(p.market_value),
                            'unrealized_pl': float(p.unrealized_pl),
                            'unrealized_plpc': float(p.unrealized_plpc),
                        }
                        for p in positions
                    ],
                    'performance': {
                        'daily_change': float(snapshot.daily_change),
                        'daily_change_pct': float(snapshot.daily_change_pct),
                    },
                    'source': 'database',
                })
        except Exception as e:
            logger.error(f"Failed to get portfolio snapshot: {e}")

        # Return empty portfolio
        return Response({
            'account': {
                'portfolio_value': 0,
                'cash': 0,
                'buying_power': 0,
                'equity': 0,
            },
            'positions': [],
            'performance': {
                'daily_change': 0,
                'daily_change_pct': 0,
            },
            'source': 'none',
        })

    def _save_snapshot(self, user, account, daily_change, daily_change_pct):
        """Save portfolio snapshot (rate limited)."""
        # Check if we should save (at most once per 5 minutes)
        last = PortfolioSnapshot.objects.filter(user=user).first()
        if last and (timezone.now() - last.timestamp).seconds < 300:
            return

        PortfolioSnapshot.objects.create(
            user=user,
            portfolio_value=account.get('portfolio_value', 0),
            cash=account.get('cash', 0),
            buying_power=account.get('buying_power', 0),
            equity=account.get('equity', 0),
            daily_change=daily_change,
            daily_change_pct=daily_change_pct,
            is_paper=user.alpaca_is_paper,
        )


class PositionsView(APIView):
    """Get current positions."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.alpaca_connected:
            try:
                service = AlpacaService.from_user(user)
                if service:
                    positions = service.get_positions()
                    return Response({'positions': positions})
            except Exception as e:
                logger.error(f"Failed to get positions: {e}")

        return Response({'positions': []})


class TradesView(APIView):
    """Get trade history."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Pagination params
        page = int(request.query_params.get('page', 1))
        limit = int(request.query_params.get('limit', 50))
        limit = min(limit, 200)
        offset = (page - 1) * limit

        trades = []

        # Get from Alpaca if connected
        if user.alpaca_connected:
            try:
                service = AlpacaService.from_user(user)
                if service:
                    alpaca_trades = service.get_orders_history(limit=100)
                    trades.extend(alpaca_trades)

                    # Sync to database
                    self._sync_trades(user, alpaca_trades)
            except Exception as e:
                logger.error(f"Failed to get trades from Alpaca: {e}")

        # Build lookup of DB trade AI analysis data (confidence, reasoning, strategy)
        db_trades = Trade.objects.filter(user=user)[:200]
        db_lookup = {t.order_id: t for t in db_trades}

        # Enrich Alpaca trades with AI analysis from DB
        for trade in trades:
            db_trade = db_lookup.get(trade.get('id'))
            if db_trade:
                trade['confidence'] = db_trade.confidence
                trade['reasoning'] = db_trade.reasoning
                trade['strategy'] = db_trade.strategy

        alpaca_ids = {t.get('id') for t in trades}

        for t in db_trades:
            if t.order_id not in alpaca_ids:
                trades.append({
                    'id': t.order_id,
                    'symbol': t.symbol,
                    'qty': t.quantity,
                    'filled_qty': t.filled_qty or 0,
                    'side': t.action,
                    'type': t.order_type,
                    'status': t.status,
                    'limit_price': float(t.limit_price) if t.limit_price else None,
                    'filled_avg_price': float(t.filled_avg_price) if t.filled_avg_price else None,
                    'created_at': t.created_at.isoformat() if t.created_at else None,
                    'confidence': t.confidence,
                    'reasoning': t.reasoning,
                    'strategy': t.strategy,
                })

        # Sort and paginate
        trades.sort(key=lambda t: t.get('created_at') or '', reverse=True)
        total = len(trades)
        trades = trades[offset:offset + limit]

        return Response({
            'trades': trades,
            'total': total,
            'page': page,
            'limit': limit,
            'has_more': offset + limit < total,
        })

    def _sync_trades(self, user, trades):
        """Sync trades from Alpaca to database."""
        for t in trades:
            Trade.objects.update_or_create(
                order_id=t['id'],
                defaults={
                    'user': user,
                    'symbol': t.get('symbol'),
                    'action': t.get('side', '').upper(),
                    'quantity': t.get('qty', 0),
                    'order_type': t.get('type', 'market'),
                    'status': t.get('status', 'pending'),
                    'limit_price': t.get('limit_price'),
                    'filled_avg_price': t.get('filled_avg_price'),
                    'filled_qty': t.get('filled_qty', 0),
                }
            )


class WatchlistView(APIView):
    """Manage user watchlist."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Seed default watchlist for new users
        if not WatchlistItem.objects.filter(user=user).exists():
            WatchlistItem.seed_default_watchlist(user)

        items = WatchlistItem.objects.filter(user=user)
        symbols = [item.symbol for item in items]

        # Get market data for symbols
        watchlist_data = []
        
        # Try Alpaca first for live data
        alpaca_service = None
        if user.alpaca_connected:
            try:
                alpaca_service = AlpacaService.from_user(user)
            except Exception as e:
                logger.error(f"Failed to init Alpaca service: {e}")

        for symbol in symbols:
            # Try Alpaca snapshot
            if alpaca_service:
                try:
                    snap = alpaca_service.get_snapshot(symbol)
                    if snap:
                        # Append and continue (skip yfinance)
                        watchlist_data.append(snap)
                        continue
                except Exception as e:
                    # Log error but don't break loop, try fallback
                    pass # limit logging noise

            # Fallback to yfinance (delayed, but has market_cap)
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                hist = ticker.history(period='2d')

                if not hist.empty:
                    current = hist['Close'].iloc[-1]
                    prev = hist['Close'].iloc[0] if len(hist) > 1 else current
                    change = current - prev
                    change_pct = (change / prev * 100) if prev else 0

                    watchlist_data.append({
                        'symbol': symbol,
                        'price': round(current, 2),
                        'change': round(change, 2),
                        'change_pct': round(change_pct, 2),
                        'prev_close': round(prev, 2),
                        'volume': int(hist['Volume'].iloc[-1]) if 'Volume' in hist else 0,
                        'market_cap': info.get('marketCap'),
                    })
                else:
                    watchlist_data.append({
                        'symbol': symbol,
                        'price': 0,
                        'change': 0,
                        'change_pct': 0,
                    })
            except Exception as e:
                logger.warning(f"Failed to get data for {symbol}: {e}")
                watchlist_data.append({
                    'symbol': symbol,
                    'price': 0,
                    'change': 0,
                    'change_pct': 0,
                })

        return Response({'watchlist': watchlist_data})

    def post(self, request):
        """Add symbol to watchlist."""
        user = request.user
        symbol = request.data.get('symbol', '').upper().strip()

        if not symbol:
            return Response(
                {'error': 'Symbol is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Watchlist size check (generous limit for all users)
        current_count = WatchlistItem.objects.filter(user=user).count()
        if current_count >= 500:
            return Response(
                {'error': 'Watchlist limit reached (500).'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Add to watchlist
        item, created = WatchlistItem.objects.get_or_create(user=user, symbol=symbol)

        return Response({
            'success': True,
            'symbol': symbol,
            'created': created,
            'message': f'{symbol} added to watchlist' if created else f'{symbol} already in watchlist'
        })

    def delete(self, request):
        """Remove symbol from watchlist."""
        user = request.user
        symbol = request.data.get('symbol', '').upper().strip()

        deleted, _ = WatchlistItem.objects.filter(user=user, symbol=symbol).delete()

        return Response({
            'success': deleted > 0,
            'symbol': symbol,
            'message': f'{symbol} removed from watchlist' if deleted else f'{symbol} not in watchlist'
        })


class MarketView(APIView):
    """Get market status."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Try Alpaca for accurate market status
        if user.alpaca_connected:
            try:
                service = AlpacaService.from_user(user)
                if service:
                    hours = service.get_market_hours()
                    return Response({
                        'is_open': hours.get('is_open', False),
                        'next_open': hours.get('next_open'),
                        'next_close': hours.get('next_close'),
                        'source': 'alpaca',
                    })
            except Exception as e:
                logger.error(f"Failed to get market status: {e}")

        # Fallback to manual check
        from zoneinfo import ZoneInfo
        et = ZoneInfo('America/New_York')
        now = datetime.now(et)

        is_open = False
        if now.weekday() < 5:  # Mon-Fri
            market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
            market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
            is_open = market_open <= now < market_close

        return Response({
            'is_open': is_open,
            'source': 'fallback',
        })


class IndicatorsView(APIView):
    """Get technical indicators for watchlist."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        advanced = True  # All indicators available to all users

        symbols = WatchlistItem.get_user_symbols(user)[:10]
        indicators = []

        for symbol in symbols:
            close = None
            current_price = 0
            
            # Try Alpaca first
            if user.alpaca_connected:
                try:
                    service = AlpacaService.from_user(user)
                    if service:
                        bars = service.get_bars(symbol, timeframe='1Day', limit=90)
                        if bars:
                            df = pd.DataFrame(bars)
                            close = df['close']
                            current_price = close.iloc[-1]
                except Exception as e:
                    # Log but continue to fallback
                    pass

            if close is None:
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period='3mo')

                    if hist.empty:
                        continue

                    close = hist['Close']
                    current_price = close.iloc[-1]
                except Exception as e:
                    logger.warning(f"Failed to calculate indicators for {symbol}: {e}")
                    continue

            try:
                # Basic indicators (free)
                rsi = self._calculate_rsi(close)
                macd, signal = self._calculate_macd(close)

                indicator_data = {
                    'symbol': symbol,
                    'price': round(current_price, 2),
                    'rsi': round(rsi, 1) if rsi else None,
                    'rsi_signal': self._rsi_signal(rsi),
                    'macd': round(macd, 4) if macd else None,
                    'macd_trend': 'BULLISH' if macd and signal and macd > signal else 'BEARISH',
                }

                # Advanced indicators (Pro+)
                if advanced:
                    sma_20 = close.rolling(20).mean().iloc[-1]
                    sma_50 = close.rolling(50).mean().iloc[-1]
                    indicator_data['sma_20'] = round(sma_20, 2)
                    indicator_data['sma_50'] = round(sma_50, 2)
                    indicator_data['above_sma_20'] = current_price > sma_20
                    indicator_data['above_sma_50'] = current_price > sma_50

                # Overall signal
                bullish = 0
                bearish = 0
                if indicator_data.get('rsi_signal') in ['OVERSOLD', 'BULLISH']:
                    bullish += 1
                elif indicator_data.get('rsi_signal') in ['OVERBOUGHT', 'BEARISH']:
                    bearish += 1
                if indicator_data.get('macd_trend') == 'BULLISH':
                    bullish += 1
                else:
                    bearish += 1

                if bullish > bearish + 1:
                    indicator_data['overall_signal'] = 'BULLISH'
                elif bearish > bullish + 1:
                    indicator_data['overall_signal'] = 'BEARISH'
                else:
                    indicator_data['overall_signal'] = 'NEUTRAL'

                indicators.append(indicator_data)

            except Exception as e:
                logger.warning(f"Failed to calculate indicators for {symbol}: {e}")

        return Response({'indicators': indicators})

    def _calculate_rsi(self, prices, period=14):
        """Calculate RSI."""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            return 100 - (100 / (1 + rs.iloc[-1]))
        except:
            return None

    def _calculate_macd(self, prices, fast=12, slow=26, signal=9):
        """Calculate MACD."""
        try:
            ema_fast = prices.ewm(span=fast).mean()
            ema_slow = prices.ewm(span=slow).mean()
            macd = ema_fast - ema_slow
            signal_line = macd.ewm(span=signal).mean()
            return macd.iloc[-1], signal_line.iloc[-1]
        except:
            return None, None

    def _rsi_signal(self, rsi):
        """Get RSI signal."""
        if rsi is None:
            return 'NEUTRAL'
        if rsi >= 70:
            return 'OVERBOUGHT'
        if rsi <= 30:
            return 'OVERSOLD'
        if rsi >= 60:
            return 'BULLISH'
        if rsi <= 40:
            return 'BEARISH'
        return 'NEUTRAL'


class OptionChainView(APIView):
    """Get option chain data."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        symbol = request.query_params.get('symbol', 'AAPL').upper()
        strike = request.query_params.get('strike')
        option_type = request.query_params.get('type', 'call').lower()

        try:
            ticker = yf.Ticker(symbol)
            current_price = ticker.history(period='1d')['Close'].iloc[-1]

            expirations = ticker.options
            if not expirations:
                return Response({'error': 'No options available'}, status=404)

            options_data = []
            target_strike = float(strike) if strike else current_price

            for exp in expirations[:8]:  # Limit to 8 expirations
                try:
                    chain = ticker.option_chain(exp)
                    opts = chain.calls if option_type == 'call' else chain.puts

                    # Find closest strike
                    opts['strike_diff'] = abs(opts['strike'] - target_strike)
                    closest = opts.loc[opts['strike_diff'].idxmin()]

                    # Calculate days to expiry
                    exp_date = datetime.strptime(exp, '%Y-%m-%d')
                    days = (exp_date - datetime.now()).days

                    last_price_val = float(closest['lastPrice'])
                    premium_pct = round(last_price_val / current_price * 100, 2) if current_price > 0 else 0
                    annualized_pct = round(premium_pct / max(days, 1) * 365, 2) if current_price > 0 else 0

                    options_data.append({
                        'expiration': exp,
                        'days_to_expiry': days,
                        'strike': float(closest['strike']),
                        'last_price': last_price_val,
                        'bid': float(closest['bid']),
                        'ask': float(closest['ask']),
                        'volume': int(closest['volume']) if closest['volume'] else 0,
                        'open_interest': int(closest['openInterest']) if closest['openInterest'] else 0,
                        'implied_volatility': float(closest['impliedVolatility']) * 100,
                        'premium_pct': premium_pct,
                        'annualized_pct': annualized_pct,
                    })
                except Exception as e:
                    logger.warning(f"Failed to get options for {exp}: {e}")

            return Response({
                'symbol': symbol,
                'current_price': round(current_price, 2),
                'strike': target_strike,
                'type': option_type,
                'options': options_data,
                'count': len(options_data),
            })

        except Exception as e:
            logger.error(f"Failed to get option chain: {e}")
            return Response({'error': str(e)}, status=500)


class CollarStrategyView(APIView):
    """Get collar strategy calculations."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        symbol = request.query_params.get('symbol', 'AAPL').upper()
        upside_pct = float(request.query_params.get('upside_pct', 5))

        try:
            ticker = yf.Ticker(symbol)
            current_price = ticker.history(period='1d')['Close'].iloc[-1]
            call_strike = current_price * (1 + upside_pct / 100)

            expirations = ticker.options[:8]
            collars = []

            for exp in expirations:
                try:
                    chain = ticker.option_chain(exp)

                    # Find call at target strike
                    calls = chain.calls
                    calls['strike_diff'] = abs(calls['strike'] - call_strike)
                    call = calls.loc[calls['strike_diff'].idxmin()]

                    # Find put that matches call premium
                    puts = chain.puts
                    call_premium = float(call['bid'])
                    puts['premium_diff'] = abs(puts['ask'] - call_premium)
                    put = puts.loc[puts['premium_diff'].idxmin()]

                    exp_date = datetime.strptime(exp, '%Y-%m-%d')
                    days = (exp_date - datetime.now()).days

                    net_cost = float(put['ask']) - float(call['bid'])
                    max_profit = float(call['strike']) - current_price - net_cost
                    max_loss = current_price - float(put['strike']) + net_cost

                    collars.append({
                        'expiration': exp,
                        'days_to_expiry': days,
                        'call_strike': float(call['strike']),
                        'call_premium': float(call['bid']),
                        'put_strike': float(put['strike']),
                        'put_premium': float(put['ask']),
                        'net_cost': round(net_cost, 2),
                        'max_profit': round(max_profit, 2),
                        'max_loss': round(max_loss, 2),
                        'protection_pct': round((current_price - float(put['strike'])) / current_price * 100, 2),
                        'upside_cap_pct': round((float(call['strike']) - current_price) / current_price * 100, 2),
                    })
                except Exception as e:
                    logger.warning(f"Failed to calculate collar for {exp}: {e}")

            return Response({
                'symbol': symbol,
                'current_price': round(current_price, 2),
                'call_strike_target': round(call_strike, 2),
                'upside_pct': upside_pct,
                'collars': collars,
                'count': len(collars),
            })

        except Exception as e:
            logger.error(f"Failed to calculate collar strategy: {e}")
            return Response({'error': str(e)}, status=500)
