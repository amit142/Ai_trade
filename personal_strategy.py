import os
from dotenv import load_dotenv
from alpaca_trade_api.rest import REST, TimeFrame
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

# Load environment variables
load_dotenv()

# Initialize API with environment variables
api = REST(
    os.getenv('ALPACA_API_KEY'),
    os.getenv('ALPACA_SECRET_KEY'),
    os.getenv('ALPACA_BASE_URL')
)

class PersonalStrategy:
    def __init__(self, initial_balance=10000):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.position = 0
        self.trades = []
        self.current_trade = None
        self.stop_loss_pct = 0.05  # 5% stop loss
        self.take_profit_pct = 0.10  # 10% take profit
        self.max_position_size = 0.2  # Maximum 20% of balance per trade
        self.rsi_period = 14
        self.rsi_overbought = 75  # Adjusted from 70
        self.rsi_oversold = 35    # Adjusted from 30
        self.ma_period = 20  # Moving average period
        self.ma_long_period = 150  # Long-term moving average period
        self.ma_threshold = 0.02  # 2% threshold for MA comparison
        self.trend_strength_threshold = 0.005  # 0.5% minimum slope for trend
        self.momentum_period = 5  # Period for momentum calculation

    def calculate_rsi(self, prices, period=14):
        """Calculate RSI for given prices"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)  # Fill NaN values with neutral RSI of 50

    def calculate_ma(self, prices, period=20):
        """Calculate moving average"""
        ma = prices.rolling(window=period).mean()
        return ma.fillna(prices)  # Fill NaN values with current price

    def calculate_volume_signal(self, volumes):
        """Calculate volume signal based on average volume"""
        avg_volume = volumes.rolling(window=10).mean()
        current_volume = volumes.iloc[-1]
        return current_volume > avg_volume.iloc[-1]

    def calculate_momentum(self, prices):
        """Calculate price momentum"""
        return prices.pct_change(self.momentum_period)

    def calculate_trend_strength(self, ma_values):
        """Calculate the strength and direction of the trend using MA slope"""
        if len(ma_values) < 5:
            return 0
        
        # Get the last 5 values as a list
        recent_ma = ma_values.tail(5).tolist()
        
        # Calculate the slope using first and last values
        if recent_ma[0] != 0:  # Prevent division by zero
            slope = (recent_ma[-1] - recent_ma[0]) / recent_ma[0]
        else:
            slope = 0
            
        return slope

    def run(self, symbol='AAPL', days=30, timeframe=TimeFrame.Day):
        """
        Run backtest for a given symbol and time period
        """
        # Calculate start and end dates
        end_date = datetime(2023, 12, 31)
        # Add extra days to account for the long MA calculation
        start_date = end_date - timedelta(days=days + self.ma_long_period + 10)  # Add buffer for trend calculation
        
        # Format dates for API
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        # Fetch historical data
        print(f"Fetching historical data for {symbol} from {start_date_str} to {end_date_str}")
        bars = api.get_bars(symbol, timeframe, start=start_date_str, end=end_date_str)
        df = pd.DataFrame([bar._raw for bar in bars])
        
        if len(df) < self.ma_long_period + 5:  # Ensure enough data for MA and trend calculation
            print("Not enough historical data to test.")
            return None
        
        # Calculate technical indicators
        df['rsi'] = self.calculate_rsi(df['c'])
        df['ma'] = self.calculate_ma(df['c'], self.ma_period)
        df['ma_long'] = self.calculate_ma(df['c'], self.ma_long_period)
        df['momentum'] = self.calculate_momentum(df['c'])
        
        # Calculate initial trends before trimming the dataframe
        full_short_trend = df['ma'].rolling(window=5).apply(
            lambda x: (x.iloc[-1] - x.iloc[0]) / x.iloc[0] if x.iloc[0] != 0 else 0
        )
        full_long_trend = df['ma_long'].rolling(window=5).apply(
            lambda x: (x.iloc[-1] - x.iloc[0]) / x.iloc[0] if x.iloc[0] != 0 else 0
        )
        
        df['short_trend'] = full_short_trend
        df['long_trend'] = full_long_trend
        
        # Only use the last 'days' rows for testing
        df = df.tail(days)
        
        # Reset state for new backtest
        self.balance = self.initial_balance
        self.position = 0
        self.trades = []
        self.current_trade = None
        
        # Analyze each period
        for i in range(1, len(df)):
            current_price = df.iloc[i]['c']
            previous_price = df.iloc[i-1]['c']
            current_rsi = df.iloc[i]['rsi']
            current_ma = df.iloc[i]['ma']
            current_ma_long = df.iloc[i]['ma_long']
            short_trend = df.iloc[i]['short_trend']
            long_trend = df.iloc[i]['long_trend']
            momentum = df.iloc[i]['momentum']
            
            print(f"\nDate: {df.iloc[i]['t']}")
            print(f"Price: ${current_price:.2f}")
            print(f"RSI: {current_rsi:.1f}")
            print(f"MA(20): ${current_ma:.2f}")
            print(f"MA(150): ${current_ma_long:.2f}")
            print(f"Short Trend: {short_trend*100:.2f}%")
            print(f"Long Trend: {long_trend*100:.2f}%")
            print(f"Momentum: {momentum*100:.2f}%")
            
            # Calculate position size based on risk
            risk_amount = self.balance * 0.01  # Risk 1% of balance per trade
            position_size = self.calculate_position_size(current_price, risk_amount)
            
            # Check volume signal if we have volume data
            volume_signal = True
            if 'v' in df.columns:
                volume_signal = self.calculate_volume_signal(df['v'].iloc[:i+1])
                print(f"Volume Signal: {'Yes' if volume_signal else 'No'}")
            
            # Entry conditions:
            # 1. Price near MA(20) (within threshold)
            # 2. Short-term trend is not strongly negative
            # 3. RSI oversold OR (RSI < 40 and positive momentum)
            # 4. Volume signal (if available)
            price_ma_diff = abs(current_price - current_ma) / current_ma
            if (self.position == 0 and 
                price_ma_diff <= self.ma_threshold and
                short_trend > -self.trend_strength_threshold and
                ((current_rsi < self.rsi_oversold) or 
                 (current_rsi < 40 and momentum > 0)) and
                volume_signal):
                
                print(f"Entry signal: Buying {position_size} shares at ${current_price:.2f}")
                print(f"Price/MA Difference: {price_ma_diff*100:.1f}%")
                print(f"Trend Analysis: Short={short_trend*100:.2f}%, Long={long_trend*100:.2f}%")
                print(f"Momentum: {momentum*100:.2f}%")
                
                # Calculate stop loss and take profit prices
                stop_loss = current_price * (1 - self.stop_loss_pct)
                take_profit = current_price * (1 + self.take_profit_pct)
                
                print(f"Stop Loss: ${stop_loss:.2f}")
                print(f"Take Profit: ${take_profit:.2f}")
                
                # Update position and balance
                self.position = position_size
                cost = position_size * current_price
                self.balance -= cost
                
                self.current_trade = {
                    'date': df.iloc[i]['t'],
                    'action': 'buy',
                    'price': current_price,
                    'shares': position_size,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit
                }
                self.trades.append(self.current_trade)
            
            # Exit conditions:
            # 1. Stop loss hit
            # 2. Take profit hit
            # 3. RSI overbought
            elif (self.position > 0 and 
                  (current_price <= self.current_trade['stop_loss'] or 
                   current_price >= self.current_trade['take_profit'] or 
                   current_rsi > self.rsi_overbought)):
                
                print(f"Exit signal: Selling {self.position} shares at ${current_price:.2f}")
                proceeds = self.position * current_price
                cost = self.current_trade['price'] * self.position
                profit = proceeds - cost
                self.balance += proceeds
                
                print(f"Trade profit/loss: ${profit:.2f}")
                
                sell_trade = {
                    'date': df.iloc[i]['t'],
                    'action': 'sell',
                    'price': current_price,
                    'shares': self.position,
                    'profit': profit
                }
                self.trades.append(sell_trade)
                self.position = 0
                self.current_trade = None
        
        # If we still have a position at the end, sell at the last price
        if self.position > 0:
            last_price = df.iloc[-1]['c']
            proceeds = self.position * last_price
            cost = self.current_trade['price'] * self.position
            profit = proceeds - cost
            self.balance += proceeds
            
            print(f"\nClosing position at end of period:")
            print(f"Selling {self.position} shares at ${last_price:.2f}")
            print(f"Trade profit/loss: ${profit:.2f}")
            
            sell_trade = {
                'date': df.iloc[-1]['t'],
                'action': 'sell',
                'price': last_price,
                'shares': self.position,
                'profit': profit
            }
            self.trades.append(sell_trade)
        
        return self._get_results()

    def calculate_position_size(self, current_price, risk_amount):
        """Calculate position size based on risk amount and stop loss"""
        risk_per_share = current_price * self.stop_loss_pct
        position_size = risk_amount / risk_per_share
        
        # Ensure it doesn't exceed max position size
        max_shares = (self.balance * self.max_position_size) / current_price
        position_size = min(position_size, max_shares)
        
        return max(1, int(position_size))  # Ensure at least 1 share

    def _get_results(self):
        """Calculate and return backtest results"""
        total_profit = sum(trade.get('profit', 0) for trade in self.trades if trade['action'] == 'sell')
        total_trades = len([t for t in self.trades if t['action'] == 'buy'])
        win_trades = len([t for t in self.trades if t['action'] == 'sell' and t.get('profit', 0) > 0])
        
        return {
            'initial_balance': self.initial_balance,
            'final_balance': self.balance,
            'total_profit': total_profit,
            'total_return': ((self.balance - self.initial_balance) / self.initial_balance) * 100,
            'number_of_trades': total_trades,
            'winning_trades': win_trades,
            'win_rate': (win_trades / total_trades * 100) if total_trades > 0 else 0,
            'trades': self.trades
        }

def print_results(results):
    """Print backtest results in a formatted way"""
    print("\nBacktest Results:")
    print(f"Initial Balance: ${results['initial_balance']:.2f}")
    print(f"Final Balance: ${results['final_balance']:.2f}")
    print(f"Total Profit/Loss: ${results['total_profit']:.2f}")
    print(f"Return: {results['total_return']:.2f}%")
    print(f"Number of Trades: {results['number_of_trades']}")
    print(f"Winning Trades: {results['winning_trades']}")
    print(f"Win Rate: {results['win_rate']:.1f}%")

if __name__ == "__main__":
    # List of stocks to test
    stocks = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']
    
    # List of time periods to test (in days)
    periods = [30, 60, 90]
    
    # Create strategy instance
    strategy = PersonalStrategy(initial_balance=10000)
    
    print("Starting backtest with multiple stocks and time periods...\n")
    
    # Test each stock and time period combination
    for stock in stocks:
        print(f"\n{'='*50}")
        print(f"Testing {stock}")
        print(f"{'='*50}")
        
        for days in periods:
            print(f"\nTesting {days} days period:")
            results = strategy.run(stock, days)
            
            if results:
                print_results(results)
                print("\nTrade Details:")
                for trade in results['trades']:
                    if trade['action'] == 'buy':
                        print(f"Buy: {trade['shares']} shares at ${trade['price']:.2f} on {trade['date']}")
                    else:
                        print(f"Sell: {trade['shares']} shares at ${trade['price']:.2f} on {trade['date']} (Profit: ${trade['profit']:.2f})")
            else:
                print("Not enough data for this period.")
            
            print("\n" + "-"*50) 