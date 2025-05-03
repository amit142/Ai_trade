import os
from dotenv import load_dotenv
from alpaca_trade_api.rest import REST, TimeFrame
import pandas as pd
from utils.risk_manager import RiskManager
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Initialize API with environment variables
api = REST(
    os.getenv('ALPACA_API_KEY'),
    os.getenv('ALPACA_SECRET_KEY'),
    os.getenv('ALPACA_BASE_URL')
)

# Initialize risk manager
risk_manager = RiskManager(api)

class Backtest:
    def __init__(self, initial_balance=10000):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.position = 0
        self.trades = []
        self.current_trade = None

    def run(self, symbol='AAPL', days=30, timeframe=TimeFrame.Day):
        """
        Run backtest for a given symbol and time period
        """
        # Calculate start and end dates - using 2023 data
        end_date = datetime(2023, 12, 31)
        start_date = datetime(2023, 12, 1)  # One month of data from December 2023
        
        # Format dates for API
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        # Fetch historical data
        print(f"Fetching historical data for {symbol} from {start_date_str} to {end_date_str}")
        bars = api.get_bars(symbol, timeframe, start=start_date_str, end=end_date_str)
        df = pd.DataFrame([bar._raw for bar in bars])
        
        if len(df) < 2:
            print("Not enough historical data to test.")
            return None
        
        # Reset state for new backtest
        self.balance = self.initial_balance
        self.position = 0
        self.trades = []
        self.current_trade = None
        
        # Analyze each period
        for i in range(1, len(df)):
            current_price = df.iloc[i]['c']
            previous_price = df.iloc[i-1]['c']
            price_diff = current_price - previous_price
            
            print(f"\nDate: {df.iloc[i]['t']}")
            print(f"Price changed from {previous_price:.2f} to {current_price:.2f} (${price_diff:.2f})")
            
            # Reset daily trades if it's a new day
            current_date = pd.to_datetime(df.iloc[i]['t']).date()
            previous_date = pd.to_datetime(df.iloc[i-1]['t']).date()
            if current_date != previous_date:
                risk_manager.reset_daily_trades()
            
            # Check if we can trade
            if not risk_manager.can_trade():
                print("Maximum daily trades reached. No action taken.")
                continue
            
            # Calculate position size based on risk
            risk_amount = self.balance * 0.01  # Risk 1% of balance per trade
            position_size = risk_manager.calculate_position_size(symbol, risk_amount)
            
            # Check if position size is within limits
            if not risk_manager.check_position_size(symbol, position_size):
                print("Position size exceeds maximum allowed. No action taken.")
                continue
            
            # Test rule: If price increased, buy
            if price_diff > 0 and self.position == 0:  # Only buy if we don't have a position
                print(f"Rule matched: Buying {position_size} shares at ${current_price:.2f}")
                
                # Calculate stop loss and take profit prices
                stop_loss = risk_manager.get_stop_loss_price(current_price)
                take_profit = risk_manager.get_take_profit_price(current_price)
                
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
                risk_manager.record_trade()
            
            # Check if we need to sell based on stop loss or take profit
            elif self.position > 0:
                if current_price <= self.current_trade['stop_loss'] or current_price >= self.current_trade['take_profit']:
                    print(f"Selling {self.position} shares at ${current_price:.2f}")
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
                    risk_manager.record_trade()
        
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

    def _get_results(self):
        """
        Calculate and return backtest results
        """
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
    """
    Print backtest results in a formatted way
    """
    print("\nBacktest Results:")
    print(f"Initial Balance: ${results['initial_balance']:.2f}")
    print(f"Final Balance: ${results['final_balance']:.2f}")
    print(f"Total Profit/Loss: ${results['total_profit']:.2f}")
    print(f"Return: {results['total_return']:.2f}%")
    print(f"Number of Trades: {results['number_of_trades']}")
    print(f"Winning Trades: {results['winning_trades']}")
    print(f"Win Rate: {results['win_rate']:.1f}%")

if __name__ == "__main__":
    # Create backtest instance
    backtest = Backtest(initial_balance=10000)
    
    # Run backtest for AAPL over the last 30 days
    results = backtest.run('AAPL', 30)
    
    if results:
        print_results(results) 