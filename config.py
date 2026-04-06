"""
量化交易系统配置文件
"""
import os

# ============== Webull API 配置 ==============
# 登录 Webull 获取
WEBULL_EMAIL = os.getenv("WEBULL_EMAIL", "")
WEBULL_PASSWORD = os.getenv("WEBULL_PASSWORD", "")
WEBULL_DEVICE_ID = os.getenv("WEBULL_DEVICE_ID", "")
WEBULL_REFRESH_TOKEN = os.getenv("WEBULL_REFRESH_TOKEN", "")

# ============== Coinbase Advanced Trade 配置 ==============
COINBASE_API_KEY = os.getenv("COINBASE_API_KEY", "")
COINBASE_API_SECRET = os.getenv("COINBASE_API_SECRET", "")
COINBASE_PASS_PHRASE = os.getenv("COINBASE_PASS_PHRASE", "")

# ============== 交易配置 ==============
# 初始资金
INITIAL_CAPITAL = 100000  # 10万美元

# 手续费配置
WEBULL_COMMISSION = 0.65  # 每手期权佣金（美元）
COINBASE_COMMISSION = 0.006  # Coinbase 手续费比例 (%)

# 滑点配置
SLIPPAGE = 0.001  # 0.1%

# ============== 回测配置 ==============
DEFAULT_START_DATE = "2024-01-01"
DEFAULT_END_DATE = "2024-12-31"

# ============== 交易品种 ==============
# 期权标的
OPTIONS_UNDERLYING = [
    "AAPL",   # 苹果
    "TSLA",   # 特斯拉
    "NVDA",   # 英伟达
    "SPY",    # S&P 500 ETF
    "QQQ",    # 纳斯达克ETF
]

# 期货品种
FUTURES_SYMBOLS = [
    "GC=F",   # 黄金期货
    "SI=F",   # 白银期货
    "ES=F",   # 标普500期货
    "NQ=F",   # 纳斯达克期货
]

# Coinbase 合约
COINBASE_CONTRACTS = {
    "GC": "GC-USD",     # 黄金
    "SI": "SI-USD",     # 白银
}
