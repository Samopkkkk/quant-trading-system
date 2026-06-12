# quant-trading-system

A quantitative auto-trading agent for US equities on **Webull**, with honest
backtesting and real risk management.

> ⚠️ **On returns:** there is no setting of this system — or any system — that
> *guarantees* a profit, let alone "100% in a month." That target decomposes
> into a *minimum* (a floor, which markets don't provide above the risk-free
> rate) and *+100%* (reachable only as a low-probability tail while accepting a
> high probability of ruin). Read **[docs/RETURNS_AND_RISK.md](docs/RETURNS_AND_RISK.md)**
> and run `python -m agent.montecarlo` before risking real money.

## Rebuilt agent (`agent/`)

The `agent/` package is the current, clean implementation. It separates concerns
so each layer is testable and auditable:

```
agent/
├── config.py      # config + risk limits (secrets from env only; paper by default)
├── types.py       # Order, Fill, Position, Signal, ...
├── data.py        # market data: Yahoo / CSV / synthetic (for tests)
├── strategies.py  # alpha: price history -> exposure (NO look-ahead)
├── risk.py        # sizing + daily-loss halt + max-drawdown kill switch
├── broker.py      # PaperBroker (offline) + WebullBroker (real OpenAPI SDK)
├── backtest.py    # event-driven backtest, honest metrics
├── engine.py      # the live/paper TradingAgent loop
├── montecarlo.py  # quantifies the return/ruin tradeoff
└── cli.py         # python -m agent.cli {backtest,paper,live}
```

### Quick start

```bash
pip install -r requirements.txt

# Offline backtest (synthetic data — no network needed)
python -m agent.cli backtest --synthetic --strategy momentum

# Real-data backtest (needs network egress to Yahoo Finance)
python -m agent.cli backtest --symbol AAPL --strategy ma_cross --range 2y

# ...or validate on your OWN data file (works offline)
python -m agent.cli backtest --symbol AAPL --csv mydata.csv --strategy ma_cross

# Walk-forward (out-of-sample) validation — the honest test for overfitting
python -m agent.cli walkforward --symbol AAPL --range 5y --strategy ma_cross

# Paper trading loop
python -m agent.cli paper --symbols AAPL,MSFT --strategy ma_cross --cycles 5 --no-sleep

# See the real cost of chasing big monthly returns
python -m agent.montecarlo

# Run the tests
python -m pytest -q
```

### Live trading on Webull

Live trading is deliberately gated. It requires:

1. `pip install webull-python-sdk-core webull-python-sdk-trade`
2. Env vars `WEBULL_APP_KEY`, `WEBULL_APP_SECRET`, `WEBULL_ACCOUNT_ID`
   (apply at https://developer.webull.com/).
3. The explicit flag `--i-understand-the-risk` *and* typing `TRADE` to confirm.

```bash
python -m agent.cli live --symbols AAPL --strategy ma_cross --i-understand-the-risk
# add --production to hit api.webull.com (REAL MONEY) instead of the UAT sandbox
```

### Environment / network note

This repo was developed in a sandbox whose egress allowlist permits **only
PyPI**. Yahoo and all Webull hosts return `403 Host not in allowlist` there, so
real-data backtests and live trading must run locally or in an environment where
those hosts are allowlisted. Details in
[docs/RETURNS_AND_RISK.md](docs/RETURNS_AND_RISK.md).

---

## Legacy modules

The directories below (`backtest/`, `strategies/`, `trading/`, `data/`, `mvp/`,
`webull/`) are the **previous** implementation, kept for reference. Note the old
live path imported `webull.core.client`, which is neither the official SDK nor
installable; the rebuilt `agent/` package supersedes it. The sections below
document that legacy system.

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
