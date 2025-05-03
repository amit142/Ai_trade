import os
from dotenv import load_dotenv
from alpaca_trade_api.rest import REST

load_dotenv()

class RiskManager:
    def __init__(self, api: REST):
        self.api = api
        self.max_position_size = float(os.getenv('MAX_POSITION_SIZE', 0.1))
        self.stop_loss_pct = float(os.getenv('STOP_LOSS_PERCENTAGE', 0.02))
        self.take_profit_pct = float(os.getenv('TAKE_PROFIT_PERCENTAGE', 0.04))
        self.max_daily_trades = int(os.getenv('MAX_DAILY_TRADES', 5))
        self.daily_trades = 0

    def check_position_size(self, symbol: str, qty: int) -> bool:
        """Check if the position size is within limits"""
        account = self.api.get_account()
        equity = float(account.equity)
        current_price = float(self.api.get_latest_trade(symbol).price)
        position_value = current_price * qty
        
        return position_value <= (equity * self.max_position_size)

    def calculate_position_size(self, symbol: str, risk_amount: float) -> int:
        """Calculate position size based on risk amount"""
        account = self.api.get_account()
        equity = float(account.equity)
        current_price = float(self.api.get_latest_trade(symbol).price)
        
        # Calculate position size based on risk amount and stop loss
        risk_per_share = current_price * self.stop_loss_pct
        position_size = risk_amount / risk_per_share
        
        # Ensure it doesn't exceed max position size
        max_shares = (equity * self.max_position_size) / current_price
        position_size = min(position_size, max_shares)
        
        return max(1, int(position_size))  # Ensure at least 1 share

    def get_stop_loss_price(self, entry_price: float) -> float:
        """Calculate stop loss price"""
        return entry_price * (1 - self.stop_loss_pct)

    def get_take_profit_price(self, entry_price: float) -> float:
        """Calculate take profit price"""
        return entry_price * (1 + self.take_profit_pct)

    def can_trade(self) -> bool:
        """Check if we can make another trade today"""
        return self.daily_trades < self.max_daily_trades

    def record_trade(self):
        """Record that a trade was made"""
        self.daily_trades += 1

    def reset_daily_trades(self):
        """Reset daily trade counter"""
        self.daily_trades = 0 