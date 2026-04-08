# Webull 量化交易机器人

基于 Webull OpenAPI 开发的量化交易机器人示例。

## 功能特性

- 账户余额和持仓查询
- 历史K线数据获取
- 实时行情订阅
- 订单下单/改单/撤单
- 持仓管理
- 多种量化策略示例

## 安装依赖

```bash
pip install webull
```

## 配置说明

在 `config.py` 中配置你的 API 凭证：
- 需要先在 Webull Developer 平台注册应用获取 App Key 和 App Secret
- 测试环境使用 `us-openapi.uat.webullbroker.com`
- 生产环境使用 `us-openapi.webullbroker.com`

## 快速开始

```python
from config import *
from trading_client import WebullTrader
from order_manager import OrderManager
from market_data import WebullMarketData

# 初始化
trader = WebullTrader(APP_KEY, APP_SECRET)
trader.set_account()

# 获取余额
balance = trader.get_account_balance()
print(f"账户余额: {balance}")

# 获取持仓
positions = trader.get_positions()
print(f"持仓: {positions}")

# 获取行情
market_data = WebullMarketData()
bars = market_data.get_history_bars("AAPL")
print(f"K线数据: {bars}")

# 下单
order_mgr = OrderManager(trader)
order_id = order_mgr.buy_limit("AAPL", 10, 150.0)
print(f"订单ID: {order_id}")
```

## 策略使用示例

```python
from strategy import MovingAverageStrategy, BreakoutStrategy, RSIStrategy

# 移动平均策略
ma_strategy = MovingAverageStrategy("AAPL", short_ma=5, long_ma=20)
signal = ma_strategy.generate_signal()
print(f"MA策略信号: {signal}")

# 突破策略
breakout = BreakoutStrategy("AAPL", period=20)
signal = breakout.generate_signal()
print(f"突破策略信号: {signal}")

# RSI策略
rsi = RSIStrategy("AAPL", period=14)
signal = rsi.generate_signal()
print(f"RSI策略信号: {signal}")
```
