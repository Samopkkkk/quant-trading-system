# quant-trading-system
Quantitative Trading System for US Stock Options, Gold & Silver Futures

## Features

### 📊 Data Sources
- **Webull API** - US stock options data and trading
- **Coinbase Advanced Trade API** - Gold/Silver futures trading
- **Yahoo Finance** - Historical data backup

### 🔧 Core Modules

```
quant-trading-system/
├── backtest/                 # Backtest engine
│   ├── __init__.py
│   ├── engine.py            # Core backtest engine
│   └── data_loader.py       # Historical data loader
├── data/                    # Data fetching
│   ├── __init__.py
│   ├── webull_client.py    # Webull API wrapper
│   └── coinbase_client.py  # Coinbase API wrapper
├── strategies/              # Trading strategies
│   ├── __init__.py
│   ├── base_strategy.py    # Base strategy class
│   ├── options_strategies.py   # Options strategies
│   ├── futures_strategies.py   # Futures strategies
│   └── advanced_strategies.py  # Advanced strategies
├── trading/                # Live trading
│   ├── __init__.py
│   ├── webull_trader.py   # Webull trader
│   └── coinbase_trader.py # Coinbase trader
├── indicators/             # Technical indicators
│   ├── __init__.py
│   └── technical.py        # Common technical indicators
├── config.py               # Configuration
├── requirements.txt        # Python dependencies
├── examples.py             # Usage examples
└── README.md
```

## Quick Start

### Install Dependencies

```bash
pip install -r requirements.txt
# Optional: for Yahoo Finance data
pip install yfinance
```

### Configure API

Edit `config.py` with your API credentials:

```python
# Webull Configuration
WEBULL_EMAIL = "your_email"
WEBULL_PASSWORD = "your_password"

# Coinbase Configuration
COINBASE_API_KEY = "your_api_key"
COINBASE_API_SECRET = "your_api_secret"
```

### Run Backtest

```python
from backtest.engine import BacktestEngine
from strategies.futures_strategies import TrendFollowingStrategy

# Initialize backtest engine
engine = BacktestEngine(initial_capital=100000)
engine.load_dataframe(your_data)

# Run strategy
strategy = TrendFollowingStrategy(symbol="GC", fast_ma=10, slow_ma=50)
engine.run_strategy(strategy)
engine.print_results()
```

## Strategy List

### Basic Futures Strategies
- **Trend Following** - MA Crossover
- **Mean Reversion** - Bollinger Bands
- **Breakout** - Channel breakout
- **Grid Trading** - Range trading

### Options Strategies
- **Covered Call** - Buy stock, sell call
- **Protective Put** - Buy stock, buy put
- **Iron Condor** - Sell call/put spread
- **Straddle** - Long volatility

### Advanced Strategies
- **Pairs Trading** - Cointegrated pairs
- **Statistical Arbitrage** - Mean reversion
- **Momentum** - Multi-MA trend
- **Factor-based** - Multi-factor model

## Live Trading

### Webull Options Trading
```python
from trading.webull_trader import WebullTrader

trader = WebullTrader(paper_trading=True)
trader.login()

# Place options order
trader.place_options_order(
    symbol="AAPL",
    quantity=1,
    strike_price=150,
    option_type="CALL",
    expiry_date="2024-12-20",
    side="SELL"
)
```

### Coinbase Futures Trading
```python
from trading.coinbase_trader import CoinbaseTrader

trader = CoinbaseTrader()

# Buy gold
trader.buy_gold(size=0.1)

# Place limit order
trader.buy_silver(size=1.0, price=25.50)
```

## Tech Stack

- **Python 3.10+**
- **pandas** - Data processing
- **numpy** - Numerical computation
- **requests** - HTTP requests
- **yfinance** - Yahoo Finance data (optional)

## Disclaimer

⚠️ This project is for educational and research purposes only. Before trading:
1. Fully understand strategy risks
2. Test with paper trading first
3. Start with small capital

## License

MIT License
