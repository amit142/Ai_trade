import pandas as pd
import pandas_ta as ta
from alpaca_trade_api.rest import REST, TimeFrame
import mplfinance as mpf

# Setup your Alpaca credentials
API_KEY = 'PKNLWPU6H5GHOBBF376X'
API_SECRET = 'sVWPIkGFBcdcCME3MUiCcu4ofJt8ZVys9jlsu3p3'
BASE_URL = 'https://paper-api.alpaca.markets'

api = REST(API_KEY, API_SECRET, BASE_URL)

def fetch_candles(symbol='amd', timeframe=TimeFrame.Minute, limit=10):
    bars = api.get_bars(symbol, timeframe, limit=limit)
    df = pd.DataFrame([bar._raw for bar in bars])
    df.rename(columns={'t': 'datetime', 'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close'}, inplace=True)
    df['datetime'] = pd.to_datetime(df['datetime'])  # <-- ADD THIS LINE
    df.sort_values('datetime', inplace=True)
    return df

def analyze_candles(df):
    open_ = df['open']
    high = df['high']
    low = df['low']
    close = df['close']

    df_patterns = ta.cdl_pattern(open_, high, low, close, name=["doji", "hammer", "spinningtop"])
    df = pd.concat([df, df_patterns], axis=1)

    for i in range(-5, 0):  # Check last 5 candles
        candle = df.iloc[i]
        found = []
        if 'CDL_DOJI' in df.columns and candle['CDL_DOJI'] != 0:
            found.append('Doji')
        if 'CDL_HAMMER' in df.columns and candle['CDL_HAMMER'] != 0:
            found.append('Hammer')
        if 'CDL_SPINNINGTOP' in df.columns and candle['CDL_SPINNINGTOP'] != 0:
            found.append('Spinning Top')

        if found:
            print(f"Candle at {candle['datetime']} matches: {', '.join(found)}")
        else:
            print(f"Candle at {candle['datetime']}: No pattern detected")

    return df

if __name__ == "__main__":
    df = fetch_candles('AAPL', TimeFrame.Minute, limit=10)
    df_with_patterns = analyze_candles(df)
    mpf.plot(df_with_patterns.set_index('datetime'), type='candle', style='charles', title="Candlestick Chart")