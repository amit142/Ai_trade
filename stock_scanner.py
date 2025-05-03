import os
from dotenv import load_dotenv
from alpaca_trade_api.rest import REST, TimeFrame
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
from typing import List, Dict, Any
import yfinance as yf

# Load environment variables
load_dotenv()

class StockScanner:
    def __init__(self, strategy_params: Dict[str, Any] = None):
        # Initialize Alpaca API (for future use with paid subscription)
        self.api = REST(
            os.getenv('ALPACA_API_KEY'),
            os.getenv('ALPACA_SECRET_KEY'),
            os.getenv('ALPACA_BASE_URL')
        )
        
        # Default strategy parameters
        self.strategy_params = strategy_params or {
            'rsi_period': 14,
            'rsi_overbought': 75,
            'rsi_oversold': 35,
            'ma_period': 20,
            'ma_long_period': 150,
            'ma_threshold': 0.02,
            'trend_strength_threshold': 0.005,
            'momentum_period': 5,
            'min_price': 10.0,
            'min_volume': 1000000,
            'min_market_cap': 1000000000,  # $1B
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'bollinger_period': 20,
            'bollinger_std': 2,
            'stochastic_period': 14,
            'stochastic_smooth': 3,
            'volume_ma_period': 20,
            'atr_period': 14
        }

    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI for given prices"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)

    def calculate_ma(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate moving average"""
        return prices.rolling(window=period).mean()

    def calculate_momentum(self, prices: pd.Series) -> pd.Series:
        """Calculate price momentum"""
        return prices.pct_change(self.strategy_params['momentum_period'])

    def calculate_macd(self, prices: pd.Series) -> tuple:
        """Calculate MACD indicator"""
        exp1 = prices.ewm(span=self.strategy_params['macd_fast'], adjust=False).mean()
        exp2 = prices.ewm(span=self.strategy_params['macd_slow'], adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=self.strategy_params['macd_signal'], adjust=False).mean()
        return macd, signal

    def calculate_bollinger_bands(self, prices: pd.Series) -> tuple:
        """Calculate Bollinger Bands"""
        ma = self.calculate_ma(prices, self.strategy_params['bollinger_period'])
        std = prices.rolling(window=self.strategy_params['bollinger_period']).std()
        upper = ma + (std * self.strategy_params['bollinger_std'])
        lower = ma - (std * self.strategy_params['bollinger_std'])
        return upper, lower

    def calculate_stochastic(self, high: pd.Series, low: pd.Series, close: pd.Series) -> tuple:
        """Calculate Stochastic Oscillator"""
        lowest_low = low.rolling(window=self.strategy_params['stochastic_period']).min()
        highest_high = high.rolling(window=self.strategy_params['stochastic_period']).max()
        k = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        d = k.rolling(window=self.strategy_params['stochastic_smooth']).mean()
        return k, d

    def calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        """Calculate Average True Range"""
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.strategy_params['atr_period']).mean()
        return atr

    def calculate_trend_strength(self, ma_values: pd.Series) -> float:
        """Calculate the strength and direction of the trend using MA slope"""
        if len(ma_values) < 5:
            return 0
        
        recent_ma = ma_values.tail(5).tolist()
        if recent_ma[0] != 0:
            slope = (recent_ma[-1] - recent_ma[0]) / recent_ma[0]
        else:
            slope = 0
            
        return slope

    def get_stock_data(self, symbol: str, days: int = 30) -> pd.DataFrame:
        """Fetch and process stock data using yfinance"""
        try:
            # Get data from yfinance
            stock = yf.Ticker(symbol)
            df = stock.history(period=f"{days + self.strategy_params['ma_long_period'] + 10}d")
            
            if len(df) < self.strategy_params['ma_long_period'] + 5:
                return None
            
            # Calculate basic indicators
            df['rsi'] = self.calculate_rsi(df['Close'], self.strategy_params['rsi_period'])
            df['ma'] = self.calculate_ma(df['Close'], self.strategy_params['ma_period'])
            df['ma_long'] = self.calculate_ma(df['Close'], self.strategy_params['ma_long_period'])
            df['momentum'] = self.calculate_momentum(df['Close'])
            
            # Calculate advanced indicators
            df['macd'], df['macd_signal'] = self.calculate_macd(df['Close'])
            df['bb_upper'], df['bb_lower'] = self.calculate_bollinger_bands(df['Close'])
            df['stoch_k'], df['stoch_d'] = self.calculate_stochastic(df['High'], df['Low'], df['Close'])
            df['atr'] = self.calculate_atr(df['High'], df['Low'], df['Close'])
            
            # Calculate volume indicators
            df['volume_ma'] = self.calculate_ma(df['Volume'], self.strategy_params['volume_ma_period'])
            df['volume_ratio'] = df['Volume'] / df['volume_ma']
            
            # Calculate trends
            df['short_trend'] = df['ma'].rolling(window=5).apply(self.calculate_trend_strength)
            df['long_trend'] = df['ma_long'].rolling(window=5).apply(self.calculate_trend_strength)
            
            return df
            
        except Exception as e:
            print(f"Error fetching data for {symbol}: {str(e)}")
            return None

    def evaluate_stock(self, symbol: str) -> Dict[str, Any]:
        """Evaluate a stock based on strategy parameters"""
        df = self.get_stock_data(symbol)
        if df is None:
            return None
        
        current_data = df.iloc[-1]
        score = 0
        signals = []
        
        # Price near MA
        price_ma_diff = abs(current_data['Close'] - current_data['ma']) / current_data['ma']
        if price_ma_diff <= self.strategy_params['ma_threshold']:
            score += 1
            signals.append("Price near MA")
        
        # RSI conditions
        if current_data['rsi'] < self.strategy_params['rsi_oversold']:
            score += 2
            signals.append("RSI oversold")
        elif current_data['rsi'] < 40 and current_data['momentum'] > 0:
            score += 1
            signals.append("RSI low with positive momentum")
        
        # MACD conditions
        if current_data['macd'] > current_data['macd_signal']:
            score += 1
            signals.append("MACD bullish")
        
        # Bollinger Bands conditions
        if current_data['Close'] < current_data['bb_lower']:
            score += 2
            signals.append("Price below lower BB")
        elif current_data['Close'] > current_data['bb_upper']:
            score -= 1
            signals.append("Price above upper BB")
        
        # Stochastic conditions
        if current_data['stoch_k'] < 20 and current_data['stoch_d'] < 20:
            score += 1
            signals.append("Stochastic oversold")
        
        # Volume conditions
        if current_data['volume_ratio'] > 1.5:
            score += 1
            signals.append("High volume")
        
        # Trend conditions
        if current_data['short_trend'] > -self.strategy_params['trend_strength_threshold']:
            score += 1
            signals.append("Positive short-term trend")
        
        if current_data['long_trend'] > 0:
            score += 1
            signals.append("Positive long-term trend")
        
        # Momentum
        if current_data['momentum'] > 0:
            score += 1
            signals.append("Positive momentum")
        
        return {
            'symbol': symbol,
            'score': score,
            'signals': signals,
            'price': current_data['Close'],
            'rsi': current_data['rsi'],
            'momentum': current_data['momentum'],
            'short_trend': current_data['short_trend'],
            'long_trend': current_data['long_trend'],
            'macd': current_data['macd'],
            'macd_signal': current_data['macd_signal'],
            'stoch_k': current_data['stoch_k'],
            'stoch_d': current_data['stoch_d'],
            'volume_ratio': current_data['volume_ratio'],
            'atr': current_data['atr']
        }

    def scan_stocks(self, symbols: List[str], filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Scan multiple stocks and return ranked results"""
        results = []
        filters = filters or {}
        
        for symbol in symbols:
            evaluation = self.evaluate_stock(symbol)
            if evaluation:
                # Apply filters
                if filters.get('min_score') and evaluation['score'] < filters['min_score']:
                    continue
                if filters.get('min_price') and evaluation['price'] < filters['min_price']:
                    continue
                if filters.get('max_price') and evaluation['price'] > filters['max_price']:
                    continue
                if filters.get('min_volume_ratio') and evaluation['volume_ratio'] < filters['min_volume_ratio']:
                    continue
                if filters.get('max_rsi') and evaluation['rsi'] > filters['max_rsi']:
                    continue
                if filters.get('min_rsi') and evaluation['rsi'] < filters['min_rsi']:
                    continue
                
                results.append(evaluation)
        
        # Sort by score in descending order
        return sorted(results, key=lambda x: x['score'], reverse=True)

    def print_scan_results(self, results: List[Dict[str, Any]]):
        """Print scan results in a formatted way"""
        print("\nStock Scanner Results:")
        print("-" * 100)
        print(f"{'Symbol':<8} {'Score':<6} {'Price':<10} {'RSI':<6} {'Momentum':<10} {'Volume':<10} {'Signals'}")
        print("-" * 100)
        
        for result in results:
            print(f"{result['symbol']:<8} {result['score']:<6} ${result['price']:<9.2f} "
                  f"{result['rsi']:<6.1f} {result['momentum']*100:<9.2f}% "
                  f"{result['volume_ratio']:<9.2f}x "
                  f"{', '.join(result['signals'])}")

if __name__ == "__main__":
    # Create scanner instance
    scanner = StockScanner()
    
    # List of stocks to scan
    stocks_to_scan = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'AMD', 'INTC', 'PYPL']
    
    # Define filters
    filters = {
        'min_price': 10.0,
        'max_price': 1000.0,
        'min_volume_ratio': 1.0,
        'min_rsi': 0,
        'max_rsi': 100
    }
    
    print("Scanning stocks...")
    results = scanner.scan_stocks(stocks_to_scan, filters)
    scanner.print_scan_results(results) 