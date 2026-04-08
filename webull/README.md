# Webull Quantitative Trading Bot

A comprehensive quantitative trading robot based on Webull OpenAPI, supporting both paper trading (simulation) and live trading.

## ⚡ Quick Start

### Paper Trading (Test Environment - Recommended!)

The easiest way to start - **no application required**:

```python
from main import QuantBot

# Paper trading mode (uses Webull's test environment)
bot = QuantBot(
    symbols=["AAPL", "TSLA", "NVDA"],
    paper_trading=True  # This uses Webull's test environment
)

# Check account
print(bot.get_account_status())

# Run strategy
signal = bot.run_strategy('MA', 'AAPL', short_ma=5, long_ma=20)

# Execute trade
result = bot.buy('AAPL', 10)
print(result)
```

### Live Trading (Production)

Requires API approval from Webull:

```python
from config import APP_KEY, APP_SECRET
from main import QuantBot

# Edit config.py to set:
# USE_PAPER_TRADING = False
# APP_KEY = "your_app_key"
# APP_SECRET = "your_app_secret"

bot = QuantBot(
    app_key=APP_KEY,
    app_secret=APP_SECRET,
    symbols=["AAPL", "TSLA"],
    paper_trading=False
)

print(bot.get_account_status())
```

## 📋 Configuration

Edit `config.py`:

```python
# Environment selection
USE_PAPER_TRADING = True  # True = Test, False = Production

# Test accounts (public, no application needed)
# Source: https://developer.webull.com/apis/docs/sdk
TEST_ACCOUNTS = [
    {
        "account_id": "J6HA4EBQRQFJD2J6NQH0F7M6",
        "app_key": "49a88f2efed4dca02b9bc1a3cecbc35dbac2895b3526cc7c7588758351ddf425d6",
        "app_secret": "..."
    },
    # ... more test accounts
]

# Production credentials (apply at https://developer.webull.com/)
APP_KEY = "your_app_key"
APP_SECRET = "your_app_secret"
```

## 🌐 Environments

| Environment | Endpoint | Account | Risk |
|-------------|----------|---------|------|
| **Test** | `us-openapi-alb.uat.webullbroker.com` | Shared test accounts | ✅ Safe |
| **Production** | `api.webull.com` | Your own account | ⚠️ Real money |

## Running the Bot

```bash
# Paper trading demo
python main.py

# Live trading (requires API approval)
python main.py --live
```

## Project Structure

```
webull/
├── config.py           # API configuration (env, credentials)
├── trading_client.py   # Trading client (live trading)
├── market_data.py      # Market data (live)
├── order_manager.py    # Order management
├── strategy.py         # Trading strategies
├── paper_trading.py   # Local paper trading simulator
├── main.py            # Main entry point
└── requirements.txt   # Dependencies
```

## 📊 Test Accounts (Shared)

Webull provides public test accounts for development:

| No. | Account ID | App Key |
|-----|------------|---------|
| 1 | J6HA4EBQRQFJD2J6NQH0F7M6 | 49a88f2efed4... |
| 2 | HBGQE8NM0CQG4Q34ABOM83HD0 | 96d9f1a0aa91... |
| 3 | BJITU00JUIVEDO5V3PRA5C5G | 8eecbf4489f4... |

Source: [Webull Developer Docs](https://developer.webull.com/apis/docs/sdk)

## Strategies

| Strategy | Description |
|----------|-------------|
| MA | Moving Average (Golden Cross/Death Cross) |
| RSI | Relative Strength Index |
| Breakout | Price breakout (N-day high/low) |
| MACD | Moving Average Convergence Divergence |
| Grid | Grid trading strategy |

## ⚠️ Disclaimer

- Paper trading is for testing only
- Quantitative trading involves risks
- Always test thoroughly before live trading
