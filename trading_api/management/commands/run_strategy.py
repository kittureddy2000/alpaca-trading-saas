
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from trading_api.services.alpaca_service import AlpacaService
from trading_api.services.ta_service import TechnicalAnalysisService
from trading_api.services.llm_trading_service import LLMTradingService
import time
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class Command(BaseCommand):
    help = 'Runs an LLM-based trading strategy for all connected users.'

    def add_arguments(self, parser):
        parser.add_argument('--symbol', type=str, default='SPY', help='Symbol to trade')
        parser.add_argument('--interval', type=int, default=60, help='Loop interval in seconds')
        parser.add_argument('--confidence', type=float, default=0.7, help='Confidence threshold (0.0 - 1.0)')

    def handle(self, *args, **options):
        symbol = options['symbol']
        interval = options['interval']
        confidence_threshold = options['confidence']
        
        self.stdout.write(self.style.SUCCESS(f'Starting AI Trading Agent for {symbol} (Interval: {interval}s, Confidence > {confidence_threshold})...'))
        
        # Initialize LLM Service once
        try:
            llm_service = LLMTradingService()
            self.stdout.write(self.style.SUCCESS('Gemini LLM Service Initialized.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to init LLM Service: {e}'))
            return

        while True:
            users = User.objects.all()
            for user in users:
                try:
                    # Get credentials
                    creds = user.get_alpaca_credentials()
                    if not creds:
                        continue 
                        
                    # Initialize service
                    service = AlpacaService(**creds)
                    
                    # Verify connection
                    try:
                        account = service.get_account()
                        if not account or account.status != 'ACTIVE':
                            continue
                    except Exception as e:
                        continue

                    self.stdout.write(f'Processing User: {user.email}')
                    
                    # 1. Get Positions
                    positions = service.get_positions()
                    has_position = False
                    if positions:
                        has_position = any(p.symbol == symbol for p in positions)
                    
                    # 2. Get Historical Data
                    # We need at least 50 bars for SMA 50, but let's get 200 for robust indicators
                    bars = service.get_bars(symbol, timeframe='1Min', limit=200)
                    
                    if not bars or len(bars) < 50:
                        self.stdout.write(self.style.WARNING(f'  Not enough data for {symbol}'))
                        continue
                        
                    # 3. Calculate Indicators
                    indicators = TechnicalAnalysisService.calculate_indicators(bars)
                    if not indicators:
                        self.stdout.write(self.style.WARNING(f'  Failed to calculate indicators.'))
                        continue

                    # Filter based on user settings
                    try:
                        from trading_api.models import UserSettings
                        settings_obj = UserSettings.get_or_create_for_user(user)
                        active_inds = settings_obj.active_indicators
                        
                        if active_inds:
                            # Map UI names to data keys
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
                            # Always include price
                            if 'price' in indicators:
                                filtered_indicators['price'] = indicators['price']
                                
                            for ui_name, is_active in active_inds.items():
                                if is_active:
                                    data_key = key_map.get(ui_name)
                                    if data_key and data_key in indicators:
                                        filtered_indicators[data_key] = indicators[data_key]
                            
                            indicators = filtered_indicators
                            self.stdout.write(f'  Using {len(indicators)-1} active indicators')
                            
                    except Exception as e:
                        logger.error(f"Error filtering indicators: {e}")
                        # Fallback to all indicators
                        
                    # 4. Get LLM Decision
                    strategy = settings_obj.strategy if 'settings_obj' in locals() else 'balanced'
                    self.stdout.write(f'  Consulting AI Analyst (Strategy: {strategy})...')
                    
                    decision = llm_service.get_trade_decision(symbol, indicators, strategy=strategy)
                    
                    action = decision.get('action', 'HOLD').upper()
                    confidence = decision.get('confidence', 0.0)
                    reasoning = decision.get('reasoning', 'No reasoning provided')
                    
                    self.stdout.write(f'  AI Decision: {action} (Confidence: {confidence:.2f})')
                    self.stdout.write(f'  Reasoning: {reasoning[:100]}...')
                    
                    # 5. Execute Trade
                    if confidence >= confidence_threshold:
                        if action == 'BUY' and not has_position:
                            self.stdout.write(self.style.SUCCESS(f'  EXECUTING BUY SIGNAL!'))
                            service.place_market_order(symbol, qty=1, side='buy')
                            
                        elif action == 'SELL' and has_position:
                             self.stdout.write(self.style.SUCCESS(f'  EXECUTING SELL SIGNAL!'))
                             service.place_market_order(symbol, qty=1, side='sell')
                        else:
                            self.stdout.write(f'  Action matches current position state (Holding: {has_position}). No trade.')
                    else:
                        self.stdout.write(f'  Confidence below threshold ({confidence_threshold}). Holding.')

                except Exception as e:
                    logger.error(f"Error processing user {user.email}: {e}")
                    self.stdout.write(self.style.ERROR(f'  Error: {e}'))

            # Sleep
            self.stdout.write(f'Sleeping for {interval}s...')
            time.sleep(interval)
