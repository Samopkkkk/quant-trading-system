"""
Quantitative Trading System Configuration
"""
import os

# ============== Webull API Configuration ==============
# Login to Webull to get these credentials
WEBULL_EMAIL = os.getenv("WEBULL_EMAIL", "")
WEBULL_PASSWORD = os.getenv("WEBULL_PASSWORD", "")
WEBULL_DEVICE_ID = os.getenv("WEBULL_DEVICE_ID", "")
WEBULL_REFRESH_TOKEN = os.getenv("WEBULL_REFRESH_TOKEN", "")

# ============== Coinbase Advanced Trade Configuration ==============
COINBASE_API_KEY = os.getenv("COINBASE_API_KEY", "")
COINBASE_API_SECRET = os.getenv("COINBASE_API_SECRET", "")
COINBASE_PASS_PHRASE = os.getenv("COINBASE_PASS_PHRASE", "")

# ============== Trading Configuration ==============
# Initial capital
INITIAL_CAPITAL = 100000  # $100,000

# Commission settings
WEBULL_COMMISSION = 0.65  # Per options contract commission (USD)
COINBASE_COMMISSION = 0.006  # Coinbase commission rate (%)

# Slippage settings
SLIPPAGE = 0.001  # 0.1%

# ============== Backtest Configuration ==============
DEFAULT_START_DATE = "2024-01-01"
DEFAULT_END_DATE = "2024-12-31"

# ============== Trading Instruments ==============
# Options underlying
OPTIONS_UNDERLYING = [
    "AAPL",   # Apple
    "TSLA",   # Tesla
    "NVDA",   # NVIDIA
    "SPY",    # S&P 500 ETF
    "QQQ",    # Nasdaq ETF
]

# Futures symbols
FUTURES_SYMBOLS = [
    "GC=F",   # Gold Futures
    "SI=F",   # Silver Futures
    "ES=F",   # S&P 500 Futures
    "NQ=F",   # Nasdaq Futures
]

# Coinbase contracts
COINBASE_CONTRACTS = {
    "GC": "GC-USD",     # Gold
    "SI": "SI-USD",     # Silver
}
