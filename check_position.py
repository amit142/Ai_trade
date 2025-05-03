from alpaca_trade_api.rest import REST

# Replace with your real (PAPER) keys
API_KEY = 'PKNLWPU6H5GHOBBF376X'
API_SECRET = 'sVWPIkGFBcdcCME3MUiCcu4ofJt8ZVys9jlsu3p3'
BASE_URL = 'https://paper-api.alpaca.markets'

# Initialize API
api = REST(API_KEY, API_SECRET, BASE_URL)

def check_position(symbol):
    try:
        position = api.get_position(symbol)
        print(f"Position in {symbol}: {position.qty} share(s) @ avg price ${position.avg_entry_price}")
    except Exception as e:
        print(f"No open position in {symbol} or error occurred: {e}")

# Example usage
if __name__ == "__main__":
    check_position('AAPL')