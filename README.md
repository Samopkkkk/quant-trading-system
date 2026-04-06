# quant-trading-system
Quantitative Trading System for US Stock Options, Gold & Silver Futures

## Features

### 📊 Data Sources
- **Webull API** - US stock options data and trading
- **Coinbase Advanced Trade API** - Gold/Silver futures trading

### 🔧 Core Modules

```
quant-trading-system/
├── backtest/                 # Backtest engine
│   ├── __init__.py
│   ├── engine.py            # Core backtest engine
│   ├── data_loader.py      # Historical data loader
│   └── analyzer.py         # Strategy analysis tools
├── data/                    # Data fetching
│   ├── __init__.py
│   ├── webull_client.py    # Webull API wrapper
│   └── coinbase_client.py  # Coinbase API wrapper
├── strategies/              # Strategy templates
│   ├── __init__.py
│   ├── base_strategy.py    # Base strategy class
│   ├── options_strategies.py   # Options strategies
│   └── futures_strategies.py   # Futures strategies
├── trading/                # Live trading
│   ├── __init__.py
│   ├── webull_trader.py   # Webull trader
│   └── coinbase_trader.py # Coinbase trader
├── indicators/             # Technical indicators
│   ├── __init__.py
│   └── technical.py        # Common technical indicators
├── config.py               # Configuration
├── requirements.txt        # Python dependencies
└── README.md
```

## Quick Start

### Install Dependencies

```bash
pip install -r requirements.txt
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
from strategies.options_strategies import IronCondorStrategy

# Initialize backtest engine
engine = BacktestEngine(
    initial_capital=100000,
    commission=0.65  # Per contract commission
)

# Load data and run backtest
engine.load_data("AAPL", "2024-01-01", "2024-12-31")
engine.run_strategy(IronCondorStrategy())
engine.print_results()
```

## Strategy List

### Options Strategies
- **Covered Call** - Buy stock, sell call options
- **Protective Put** - Buy stock, buy put options
- **Iron Condor** - Sell call spread + put spread
- **Iron Butterfly** - Buy call spread + put spread
- **Straddle/Strangle** - Long/Short volatility strategies

### Futures Strategies
- **Trend Following** - Moving average crossover
- **Mean Reversion** - Bollinger Bands strategy
- **Arbitrage** - Cross-exchange spread trading

## Tech Stack

- **Python 3.10+**
- **pandas** - Data processing
- **numpy** - Numerical computation
- **requests** - HTTP requests
- **ccxt** - Unified exchange interface

## Disclaimer

⚠️ This project is for educational and research purposes only. Before using:
1. Fully understand strategy risks
2. Test with paper trading/first
3. Start with small capital

## License

MIT License
