# quant-trading-system
美股期权及黄金白银期货量化交易系统 - 回测+实盘

## 功能特性

### 📊 数据源
- **Webull API** - 美股期权数据获取与交易
- **Coinbase Advanced Trade API** - 黄金/白银期货交易

### 🔧 核心模块

```
quant-trading-system/
├── backtest/                 # 回测引擎
│   ├── __init__.py
│   ├── engine.py            # 回测核心引擎
│   ├── data_loader.py      # 历史数据加载
│   └── analyzer.py         # 策略分析工具
├── data/                    # 数据获取
│   ├── __init__.py
│   ├── webull_client.py    # Webull API 封装
│   └── coinbase_client.py  # Coinbase API 封装
├── strategies/              # 策略模板
│   ├── __init__.py
│   ├── base_strategy.py    # 基础策略类
│   ├── options_strategies.py   # 期权策略
│   └── futures_strategies.py   # 期货策略
├── trading/                # 实盘交易
│   ├── __init__.py
│   ├── webull_trader.py   # Webull 实盘
│   └── coinbase_trader.py # Coinbase 实盘
├── indicators/             # 技术指标
│   ├── __init__.py
│   └── technical.py        # 常用技术指标
├── config.py               # 配置文件
├── requirements.txt        # Python 依赖
└── README.md
```

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置 API

编辑 `config.py` 填入你的 API 凭证：

```python
# Webull 配置
WEBULL_EMAIL = "your_email"
WEBULL_PASSWORD = "your_password"

# Coinbase 配置
COINBASE_API_KEY = "your_api_key"
COINBASE_API_SECRET = "your_api_secret"
```

### 运行回测

```python
from backtest.engine import BacktestEngine
from strategies.options_strategies import IronCondorStrategy

# 初始化回测引擎
engine = BacktestEngine(
    initial_capital=100000,
    commission=0.65  # 每手期权佣金
)

# 加载数据并回测
engine.load_data("AAPL", "2024-01-01", "2024-12-31")
engine.run_strategy(IronCondorStrategy())
engine.print_results()
```

## 策略列表

### 期权策略
- **Covered Call** - 备兑看涨期权
- **Protective Put** - 保护性看跌期权
- **Iron Condor** - 铁鹰策略
- **Iron Butterfly** - 铁蝶策略
- **Straddle/Strangle** - 跨式/宽跨式策略

### 期货策略
- **趋势跟踪** - 均线交叉策略
- **均值回归** - 布林带策略
- **套利** - 跨交易所价差策略

## 技术栈

- **Python 3.10+**
- **pandas** - 数据处理
- **numpy** - 数值计算
- **requests** - HTTP 请求
- **ccxt** - 统一交易所接口

## 注意事项

⚠️ 本项目仅供学习研究，使用前请务必：
1. 充分理解策略风险
2. 先用模拟盘/回测验证
3. 小资金实盘测试

## License

MIT License
