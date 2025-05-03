# AI Trading Bot

An autonomous trading bot that uses machine learning and technical analysis to make trading decisions.

## Project Structure
```
ai_trader/
├── config/              # Configuration files
├── data/               # Data storage
├── models/             # ML models
├── strategies/         # Trading strategies
├── utils/              # Utility functions
└── main.py            # Main entry point
```

## Features
- Technical analysis
- Machine learning predictions
- Risk management
- Paper trading with Alpaca
- Backtesting framework

## Setup
1. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your Alpaca API keys
```

## Usage
```bash
python main.py
```
