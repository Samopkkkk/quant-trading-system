# Webull Quantitative Trading Bot

A comprehensive quantitative trading robot based on Webull OpenAPI, supporting both paper trading (simulation) and live trading.

## Features

- **Trading API**: Account balance, positions, order management
- **Market Data**: Historical K-line, real-time quotes, batch queries
- **Order Management**: Place/modify/cancel orders (limit/market)
- **Multiple Strategies**: MA, RSI, MACD, Breakout, Grid trading
- **Paper Trading**: Test strategies without real money

## Installation

```bash
pip install webull
```

## Quick Start

### Paper Trading (No API Key Required)

```python
from main import QuantBot

# Create paper trading bot (simulation)
bot = QuantBot(
    symbols=["AAPL", "TSLA", "NVDA"],
    paper_trading=True,
    initial_cash=100000.0
)

# Check account
print(bot.get_account_status())

# Run strategy
signal = bot.run_strategy('MA', 'AAPL', short_ma=5, long_ma=20)
print(f"Signal: {signal}")

# Execute trade
result = bot.buy('AAPL', 10)
print(result)

# Simulate days passing
for i in range(30):
    bot.next_day()

# Check portfolio
print(bot.get_balance())
print(bot.get_positions_summary())
```

### Live Trading (Requires API Key)

```python
from config import APP_KEY, APP_SECRET
from main import QuantBot

# Create live trading bot
bot = QuantBot(
    app_key=APP_KEY,
    app_secret=APP_SECRET,
    symbols=["AAPL", "TSLA"],
    paper_trading=False
)

# Check account
print(bot.get_account_status())

# Execute trade
result = bot.buy("AAPL", 10, limit_price=150.0)
```

## Configuration

Edit `config.py` with your Webull API credentials:

```python
APP_KEY = "your_app_key"
APP_SECRET = "your_app_secret"

# Test environment
API_ENDPOINT = "us-openapi.uat.webullbroker.com"

# Production environment
# API_ENDPOINT = "us-openapi.webullbroker.com"
```

Get your API key from [Webull Developer Portal](https://developer.webull.com/)

## Running the Bot

```bash
# Paper trading demo (default)
python main.py

# Live trading (requires API key)
python main.py --live
```

## Project Structure

```
webull/
├── config.py           # API configuration
├── trading_client.py   # Trading client (live)
├── market_data.py      # Market data (live)
├── order_manager.py    # Order management
├── strategy.py         # Trading strategies
├── paper_trading.py   # Paper trading simulator
├── main.py            # Main entry point
└── requirements.txt   # Dependencies
```

## Strategies

| Strategy | Description |
|----------|-------------|
| MA | Moving Average (Golden Cross/Death Cross) |
| RSI | Relative Strength Index |
| Breakout | Price breakout (N-day high/low) |
| MACD | Moving Average Convergence Divergence |
| Grid | Grid trading strategy |

## Paper Trading Features

- ✅ No API key required
- ✅ Simulated market prices with realistic volatility
- ✅ Track portfolio value over time
- ✅ Test strategies without risk
- ✅ Full order history and P&L tracking

## Disclaimer

⚠️ Quantitative trading involves risks. Use paper trading for testing before going live.
