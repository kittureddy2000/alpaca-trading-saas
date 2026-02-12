
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

class TechnicalAnalysisService:
    """
    Service to calculate technical indicators from raw market data.
    """

    @staticmethod
    def calculate_indicators(bars) -> dict:
        """
        Calculate all requested indicators for the given bars.
        
        Args:
            bars: List of Alpaca Bar objects or dictionary.
            
        Returns:
            dict: Structured indicators.
        """
        try:
            # Convert to DataFrame
            data = []
            for bar in bars:
                # Handle both object and dict representation
                if hasattr(bar, 'timestamp'):
                    d = {
                        'timestamp': bar.timestamp,
                        'open': float(bar.open),
                        'high': float(bar.high),
                        'low': float(bar.low),
                        'close': float(bar.close),
                        'volume': float(bar.volume),
                        'vwap': float(bar.vwap) if bar.vwap else 0
                    }
                else:
                    d = bar
                data.append(d)
                
            df = pd.DataFrame(data)
            if df.empty:
                return {}
                
            # Ensure chronological order
            df = df.sort_values('timestamp')
            
            # --- Indicators ---
            
            # 1. RSI (14)
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # 2. MACD (12, 26, 9)
            ema12 = df['close'].ewm(span=12, adjust=False).mean()
            ema26 = df['close'].ewm(span=26, adjust=False).mean()
            df['macd_line'] = ema12 - ema26
            df['macd_signal'] = df['macd_line'].ewm(span=9, adjust=False).mean()
            df['macd_hist'] = df['macd_line'] - df['macd_signal']
            
            # 3. SMA (20, 50)
            df['sma_20'] = df['close'].rolling(window=20).mean()
            df['sma_50'] = df['close'].rolling(window=50).mean()
            
            # 4. EMA (12, 26) - Already calc for MACD, verify logic if used independently
            df['ema_12'] = ema12 
            df['ema_26'] = ema26
            
            # 5. Bollinger Bands (20, 2.0)
            df['bb_mid'] = df['close'].rolling(window=20).mean()
            df['bb_std'] = df['close'].rolling(window=20).std()
            df['bb_upper'] = df['bb_mid'] + (2 * df['bb_std'])
            df['bb_lower'] = df['bb_mid'] - (2 * df['bb_std'])
            
            # 6. Volume Analysis (20-day avg) - using whatever resolution bars are (e.g. 1Min)
            df['vol_avg_20'] = df['volume'].rolling(window=20).mean()
            
            # 7. ATR (14)
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = np.max(ranges, axis=1)
            df['atr'] = true_range.rolling(window=14).mean()
            
            # 8. VWAP (Intraday) - Alpaca bars often come with 'vwap' field.
            # If calculating manually from start of 'day' in this df:
            df['vwap_calc'] = (df['volume'] * (df['high'] + df['low'] + df['close']) / 3).cumsum() / df['volume'].cumsum()
            # Use provided vwap if available and non-zero, else calc
            df['final_vwap'] = df.apply(lambda row: row['vwap'] if row.get('vwap') else row['vwap_calc'], axis=1)
            
            # 9. Price Changes
            df['pct_change_1'] = df['close'].pct_change(periods=1) * 100
            df['pct_change_5'] = df['close'].pct_change(periods=5) * 100
            df['pct_change_20'] = df['close'].pct_change(periods=20) * 100
            
            # Get latest row
            latest = df.iloc[-1]
            
            return {
                'price': latest['close'],
                'rsi': latest['rsi'],
                'macd': {
                    'line': latest['macd_line'],
                    'signal': latest['macd_signal'],
                    'histogram': latest['macd_hist']
                },
                'sma': {
                    'sma_20': latest['sma_20'],
                    'sma_50': latest['sma_50']
                },
                'ema': {
                    'ema_12': latest['ema_12'],
                    'ema_26': latest['ema_26']
                },
                'bollinger': {
                    'upper': latest['bb_upper'],
                    'middle': latest['bb_mid'],
                    'lower': latest['bb_lower']
                },
                'volume': {
                    'current': latest['volume'],
                    'avg_20': latest['vol_avg_20']
                },
                'vwap': latest['final_vwap'],
                'atr': latest['atr'],
                'changes': {
                    'change_1': latest['pct_change_1'],
                    'change_5': latest['pct_change_5'],
                    'change_20': latest['pct_change_20']
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return {}
