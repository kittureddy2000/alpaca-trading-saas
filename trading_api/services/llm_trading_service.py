
import google.generativeai as genai
import logging
import json
from django.conf import settings

logger = logging.getLogger(__name__)

class LLMTradingService:
    """
    Service to get trading decisions from Google Gemini LLM.
    """

    def __init__(self):
        # Configure Gemini
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            logger.error("GEMINI_API_KEY not found in settings.")
            raise ValueError("GEMINI_API_KEY is missing")
            
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')

    def get_trade_decision(self, symbol: str, indicators: dict, strategy: str = 'balanced') -> dict:
        """
        Ask LLM for a trading decision based on technical indicators and user strategy.
        
        Args:
            symbol: Stock symbol (e.g. 'SPY')
            indicators: Dictionary of calculated indicators.
            strategy: User defined strategy (balanced, aggressive, conservative)
            
        Returns:
            dict: {
                'action': 'BUY' | 'SELL' | 'HOLD',
                'confidence': float (0.0 - 1.0),
                'reasoning': str
            }
        """
        if not indicators:
            return {'action': 'HOLD', 'confidence': 0.0, 'reasoning': 'No data available'}

        prompt = self._construct_prompt(symbol, indicators, strategy)
        
        try:
            response = self.model.generate_content(prompt)
            # Clean up response to ensure valid JSON
            text = response.text.strip()
            # Remove any markdown code block formatting if present
            if text.startswith('```json'):
                text = text[7:]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()
            
            decision = json.loads(text)
            return decision
        except Exception as e:
            logger.error(f"Error getting LLM decision for {symbol}: {e}")
            return {'action': 'HOLD', 'confidence': 0.0, 'reasoning': f"LLM Error: {e}"}

    def _construct_prompt(self, symbol: str, data: dict, strategy: str) -> str:
        """Construct the prompt for the LLM."""
        
        strategy_desc = {
            'aggressive': 'Prioritize growth. Take trades with lower confidence (0.6+) if potential upside is high. Favor momentum indicators.',
            'conservative': 'Prioritize capital preservation. Only take trades with very high confidence (0.8+) and strong confluence. Avoid volatile setups.',
            'balanced': 'Balance risk and reward. Look for good confluence with confidence > 0.7.'
        }
        
        current_strategy = strategy_desc.get(strategy.lower(), strategy_desc['balanced'])
        
        return f"""
        You are an expert algorithmic trading agent. Your job is to analyze the technical indicators for {symbol} and decide whether to BUY, SELL, or HOLD.
        
        User Strategy: {strategy.upper()}
        Strategy Instructions: {current_strategy}
        
        Current Market Data:
        Price: ${data.get('price', 'N/A')}
        
        Technical Indicators:
        1. RSI (14): {data.get('rsi', 'N/A')} 
           (>70 Overbought, <30 Oversold)
           
        2. MACD:
           Line: {data.get('macd', {}).get('line', 'N/A')}
           Signal: {data.get('macd', {}).get('signal', 'N/A')}
           Histogram: {data.get('macd', {}).get('histogram', 'N/A')}
           (Line > Signal is Bullish)
           
        3. Moving Averages:
           SMA 20: ${data.get('sma', {}).get('sma_20', 'N/A')}
           SMA 50: ${data.get('sma', {}).get('sma_50', 'N/A')}
           (Price > SMA is Bullish, SMA 20 > SMA 50 is Golden Cross)
           
        4. Bollinger Bands:
           Upper: ${data.get('bollinger', {}).get('upper', 'N/A')}
           Middle: ${data.get('bollinger', {}).get('middle', 'N/A')}
           Lower: ${data.get('bollinger', {}).get('lower', 'N/A')}
           
        5. Volume:
           Current: {data.get('volume', {}).get('current', 'N/A')}
           20-Day Avg: {data.get('volume', {}).get('avg_20', 'N/A')}
           
        6. VWAP: ${data.get('vwap', 'N/A')}
        
        7. ATR (Volatility): {data.get('atr', 'N/A')}
        
        Instructions:
        - Analyze all indicators together. Look for confluence.
        - STRICTLY follow the User Strategy guidelines defined above.
        - Provide a confidence score between 0.0 and 1.0.
        - Return ONLY valid JSON in the following format:
        
        {{
            "action": "BUY" | "SELL" | "HOLD",
            "confidence": 0.85,
            "reasoning": "Strategy aligned reasoning..."
        }}
        """
