
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from trading_api.services.alpaca_service import AlpacaService
from trading_api.services.ta_service import TechnicalAnalysisService
from trading_api.services.llm_trading_service import LLMTradingService
from trading_api.models import UserSettings, Trade
import time
import logging
import uuid

logger = logging.getLogger(__name__)
User = get_user_model()

class Command(BaseCommand):
    help = 'Runs an LLM-based trading strategy for all connected users.'

    def add_arguments(self, parser):
        parser.add_argument('--symbol', type=str, default='SPY', help='Symbol to trade')
        parser.add_argument('--interval', type=int, default=60, help='Loop interval in seconds')
        parser.add_argument('--confidence', type=float, default=0.0, help='Override confidence threshold (0 = use per-user settings)')
        parser.add_argument('--once', action='store_true', help='Run once and exit (for Cloud Run Jobs)')

    def handle(self, *args, **options):
        symbol = options['symbol']
        interval = options['interval']
        confidence_override = options['confidence']
        run_once = options['once']

        self.stdout.write(self.style.SUCCESS(
            f'Starting AI Trading Agent for {symbol} '
            f'(Interval: {interval}s, Mode: {"once" if run_once else "loop"})...'
        ))

        # Initialize LLM Service once
        try:
            llm_service = LLMTradingService()
            self.stdout.write(self.style.SUCCESS('Gemini LLM Service Initialized.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to init LLM Service: {e}'))
            return

        if run_once:
            self._run_cycle(symbol, confidence_override, llm_service)
        else:
            while True:
                self._run_cycle(symbol, confidence_override, llm_service)
                self.stdout.write(f'Sleeping for {interval}s...')
                time.sleep(interval)

    def _run_cycle(self, symbol, confidence_override, llm_service):
        """Run one analysis cycle for all users."""
        users = User.objects.all()
        processed = 0
        traded = 0

        for user in users:
            try:
                result = self._process_user(user, symbol, confidence_override, llm_service)
                if result:
                    processed += 1
                    if result.get('traded'):
                        traded += 1
            except Exception as e:
                logger.error(f"Error processing user {user.email}: {e}")
                self.stdout.write(self.style.ERROR(f'  Error for {user.email}: {e}'))

        self.stdout.write(self.style.SUCCESS(
            f'Cycle complete: {processed} users processed, {traded} trades executed'
        ))

    def _process_user(self, user, symbol, confidence_override, llm_service):
        """Process a single user: analyze and potentially trade."""
        # Get credentials
        creds = user.get_alpaca_credentials()
        if not creds:
            return None

        # Initialize service
        service = AlpacaService(**creds)

        # Verify connection
        try:
            account = service.get_account()
            if not account or account.get('status') != 'ACTIVE':
                return None
        except Exception:
            return None

        self.stdout.write(f'Processing User: {user.email}')

        # Get user settings
        try:
            settings_obj = UserSettings.get_or_create_for_user(user)
        except Exception:
            settings_obj = None

        # Determine confidence threshold (override > per-user setting > default 0.7)
        if confidence_override > 0:
            confidence_threshold = confidence_override
        elif settings_obj:
            confidence_threshold = settings_obj.min_confidence or 0.7
        else:
            confidence_threshold = 0.7

        # 1. Get Positions
        positions = service.get_positions()
        has_position = False
        if positions:
            has_position = any(p.get('symbol') == symbol for p in positions)

        # 2. Get Historical Data (200 bars for robust indicators)
        bars = service.get_bars(symbol, timeframe='1Min', limit=200)

        if not bars or len(bars) < 50:
            self.stdout.write(self.style.WARNING(f'  Not enough data for {symbol}'))
            return None

        # 3. Calculate Indicators
        indicators = TechnicalAnalysisService.calculate_indicators(bars)
        if not indicators:
            self.stdout.write(self.style.WARNING(f'  Failed to calculate indicators.'))
            return None

        # 4. Filter based on user's active_indicators settings
        if settings_obj:
            try:
                active_inds = settings_obj.active_indicators
                if active_inds:
                    key_map = {
                        'RSI': 'rsi',
                        'MACD': 'macd',
                        'SMA': 'sma',
                        'EMA': 'ema',
                        'Bollinger Bands': 'bollinger',
                        'Volume Analysis': 'volume',
                        'VWAP': 'vwap',
                        'ATR': 'atr',
                        'Price Changes': 'changes',
                    }

                    filtered_indicators = {}
                    if 'price' in indicators:
                        filtered_indicators['price'] = indicators['price']

                    for ui_name, is_active in active_inds.items():
                        if is_active:
                            data_key = key_map.get(ui_name)
                            if data_key and data_key in indicators:
                                filtered_indicators[data_key] = indicators[data_key]

                    active_names = [k for k, v in active_inds.items() if v]
                    indicators = filtered_indicators
                    self.stdout.write(f'  Active indicators: {", ".join(active_names)}')
            except Exception as e:
                logger.error(f"Error filtering indicators for {user.email}: {e}")

        # 5. Get LLM Decision
        strategy = settings_obj.strategy if settings_obj else 'balanced'
        self.stdout.write(f'  Consulting AI (Strategy: {strategy}, Threshold: {confidence_threshold:.0%})...')

        decision = llm_service.get_trade_decision(symbol, indicators, strategy=strategy)

        action = decision.get('action', 'HOLD').upper()
        confidence = decision.get('confidence', 0.0)
        reasoning = decision.get('reasoning', 'No reasoning provided')

        self.stdout.write(f'  Decision: {action} (Confidence: {confidence:.2f})')
        self.stdout.write(f'  Reasoning: {reasoning[:150]}...')

        # 6. Execute Trade and Log to DB
        traded = False
        if confidence >= confidence_threshold:
            if action == 'BUY' and not has_position:
                self.stdout.write(self.style.SUCCESS(f'  EXECUTING BUY for {symbol}!'))
                try:
                    order = service.place_market_order(symbol, qty=1, side='buy')
                    self._save_trade(user, order, confidence, reasoning, strategy)
                    traded = True
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  Order failed: {e}'))
                    self._save_failed_trade(user, symbol, 'BUY', confidence, reasoning, strategy, str(e))

            elif action == 'SELL' and has_position:
                self.stdout.write(self.style.SUCCESS(f'  EXECUTING SELL for {symbol}!'))
                try:
                    order = service.place_market_order(symbol, qty=1, side='sell')
                    self._save_trade(user, order, confidence, reasoning, strategy)
                    traded = True
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  Order failed: {e}'))
                    self._save_failed_trade(user, symbol, 'SELL', confidence, reasoning, strategy, str(e))
            else:
                self.stdout.write(f'  No action needed (Position: {has_position}, Signal: {action})')
                # Log HOLD decisions with reasoning for audit trail
                self._save_hold_decision(user, symbol, action, confidence, reasoning, strategy, has_position)
        else:
            self.stdout.write(f'  Confidence {confidence:.2f} < threshold {confidence_threshold:.2f}. Holding.')
            self._save_hold_decision(user, symbol, 'HOLD', confidence, reasoning, strategy, has_position)

        return {'traded': traded, 'action': action, 'confidence': confidence}

    def _save_trade(self, user, order, confidence, reasoning, strategy):
        """Save an executed trade with AI decision data."""
        try:
            Trade.objects.update_or_create(
                order_id=order.get('id', str(uuid.uuid4())),
                defaults={
                    'user': user,
                    'symbol': order.get('symbol', ''),
                    'action': order.get('side', '').upper(),
                    'quantity': int(order.get('qty', 1)),
                    'order_type': order.get('type', 'market'),
                    'status': order.get('status', 'pending'),
                    'filled_avg_price': order.get('filled_avg_price'),
                    'filled_qty': int(order.get('filled_qty', 0)),
                    'confidence': confidence,
                    'reasoning': reasoning,
                    'strategy': strategy,
                }
            )
            self.stdout.write(f'  Trade saved to DB with confidence={confidence:.2f}')
        except Exception as e:
            logger.error(f"Failed to save trade: {e}")

    def _save_failed_trade(self, user, symbol, action, confidence, reasoning, strategy, error_msg):
        """Save a failed trade attempt for audit."""
        try:
            Trade.objects.create(
                order_id=str(uuid.uuid4()),
                user=user,
                symbol=symbol,
                action=action,
                quantity=1,
                order_type='market',
                status='rejected',
                confidence=confidence,
                reasoning=f'{reasoning} [ERROR: {error_msg}]',
                strategy=strategy,
            )
        except Exception as e:
            logger.error(f"Failed to save failed trade: {e}")

    def _save_hold_decision(self, user, symbol, action, confidence, reasoning, strategy, has_position):
        """Save HOLD decisions for audit trail (optional, only for significant decisions)."""
        # Only log hold decisions that met confidence but had no trade opportunity
        # to avoid flooding the DB with every cycle's HOLD
        if confidence >= 0.5:
            try:
                Trade.objects.create(
                    order_id=f'hold-{uuid.uuid4().hex[:12]}',
                    user=user,
                    symbol=symbol,
                    action=action,
                    quantity=0,
                    order_type='market',
                    status='hold',
                    confidence=confidence,
                    reasoning=reasoning,
                    strategy=strategy,
                )
            except Exception as e:
                logger.error(f"Failed to save hold decision: {e}")
