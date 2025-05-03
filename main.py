import os
from dotenv import load_dotenv
from alpaca_trade_api.rest import REST, TimeFrame
import pandas as pd
from utils.risk_manager import RiskManager

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

def main():
    symbol = 'AAPL'  # You can change this
    risk_amount = 1000  # Amount to risk per trade in USD

    # Fetch the most recent 1-minute bars
    bars = api.get_bars(symbol, TimeFrame.Minute, limit=3)
    df = pd.DataFrame([bar._raw for bar in bars])

    if len(df) < 2:
        print("Not enough minute data to test.")
        return

    latest_close = df.iloc[-1]['c']
    previous_close = df.iloc[-2]['c']
    price_diff = latest_close - previous_close

    print(f"Price changed from {previous_close} to {latest_close} (${price_diff:.2f})")

    # Check if we can trade
    if not risk_manager.can_trade():
        print("Maximum daily trades reached. No action taken.")
        return

    # Calculate position size based on risk
    position_size = risk_manager.calculate_position_size(symbol, risk_amount)

    # Check if position size is within limits
    if not risk_manager.check_position_size(symbol, position_size):
        print("Position size exceeds maximum allowed. No action taken.")
        return

    # Test rule: If price increased, buy
    if price_diff > 0:
        print(f"Rule matched: Placing buy order for {position_size} shares")
        
        # Calculate stop loss and take profit prices
        stop_loss = risk_manager.get_stop_loss_price(latest_close)
        take_profit = risk_manager.get_take_profit_price(latest_close)
        
        print(f"Stop Loss: ${stop_loss:.2f}")
        print(f"Take Profit: ${take_profit:.2f}")
        
        # Place the order
        api.submit_order(
            symbol=symbol,
            qty=position_size,
            side='buy',
            type='market',
            time_in_force='gtc',
            stop_loss=stop_loss,
            take_profit=take_profit
        )
    else:
        print("Rule not matched: No action taken")

if __name__ == "__main__":
    main()    
    
    