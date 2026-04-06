"""
量化交易系统示例代码
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 导入回测引擎
from backtest.engine import BacktestEngine, run_backtest

# 导入策略
from strategies.options_strategies import (
    IronCondorStrategy,
    CoveredCallStrategy,
    ProtectivePutStrategy,
    StraddleStrategy
)
from strategies.futures_strategies import (
    TrendFollowingStrategy,
    MeanReversionStrategy,
    BreakoutStrategy
)

# 导入数据客户端
from data.webull_client import WebullClient
from data.coinbase_client import CoinbaseClient


def generate_sample_data(symbol: str = "SPY", days: int = 365) -> pd.DataFrame:
    """
    生成示例数据 (模拟)
    
    实际使用时，请使用真实API获取数据
    """
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    
    # 模拟价格走势 (随机游走 + 趋势)
    np.random.seed(42)
    returns = np.random.randn(days) * 0.02
    trend = np.linspace(0, 0.1, days)  # 轻微上涨趋势
    
    price = 100 * np.exp(np.cumsum(returns + trend))
    
    # 生成OHLC数据
    data = pd.DataFrame({
        'date': dates,
        'open': price * (1 + np.random.randn(days) * 0.01),
        'high': price * (1 + np.abs(np.random.randn(days)) * 0.02),
        'low': price * (1 - np.abs(np.random.randn(days)) * 0.02),
        'close': price,
        'volume': np.random.randint(1000000, 10000000, days)
    })
    
    data.set_index('date', inplace=True)
    return data


# ============== 示例 1: 基础回测 ==============
def example_basic_backtest():
    """基础回测示例"""
    print("=" * 50)
    print("示例 1: 基础回测")
    print("=" * 50)
    
    # 生成示例数据
    data = generate_sample_data("SPY", 365)
    
    # 创建回测引擎
    engine = BacktestEngine(initial_capital=100000)
    
    # 加载数据
    engine.load_dataframe(data)
    
    # 设置策略
    strategy = TrendFollowingStrategy(symbol="SPY", fast_ma=10, slow_ma=50)
    engine.set_strategy(strategy)
    
    # 运行回测
    engine.run_strategy()
    
    # 打印结果
    engine.print_results()
    
    return engine.get_results()


# ============== 示例 2: 期权策略回测 ==============
def example_options_backtest():
    """期权策略回测示例"""
    print("\n" + "=" * 50)
    print("示例 2: 期权策略回测")
    print("=" * 50)
    
    # 生成标的资产数据
    data = generate_sample_data("AAPL", 365)
    
    engine = BacktestEngine(initial_capital=100000, commission=0.65)
    engine.load_dataframe(data)
    
    # 备兑看涨期权策略
    strategy = CoveredCallStrategy(underlying="AAPL")
    engine.set_strategy(strategy)
    
    engine.run_strategy()
    engine.print_results()
    
    return engine.get_results()


# ============== 示例 3: 黄金期货策略 ==============
def example_gold_futures():
    """黄金期货策略示例"""
    print("\n" + "=" * 50)
    print("示例 3: 黄金期货策略")
    print("=" * 50)
    
    # 黄金价格数据 (示例)
    data = generate_sample_data("GC", 365)
    
    engine = BacktestEngine(initial_capital=50000)
    engine.load_dataframe(data)
    
    # 布林带均值回归策略
    strategy = MeanReversionStrategy(symbol="GC", period=20, std_dev=2.0)
    engine.set_strategy(strategy)
    
    engine.run_strategy()
    engine.print_results()
    
    return engine.get_results()


# ============== 示例 4: 使用真实API数据 ==============
def example_with_real_data():
    """使用真实API数据示例"""
    print("\n" + "=" * 50)
    print("示例 4: 使用真实API数据")
    print("=" * 50)
    
    # Coinbase 客户端
    client = CoinbaseClient()
    
    # 获取黄金价格数据
    candles = client.get_gold_candles(granularity=3600, hours=168)  # 最近一周
    
    if candles:
        # 转换为DataFrame
        df = pd.DataFrame(candles)
        df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        df['date'] = pd.to_datetime(df['timestamp'], unit='s')
        df.set_index('date', inplace=True)
        df = df.sort_index()
        
        print(f"获取到 {len(df)} 条K线数据")
        print(df.tail())
        
        # 运行回测
        engine = BacktestEngine(initial_capital=50000)
        engine.load_dataframe(df)
        
        strategy = TrendFollowingStrategy(symbol="GC", fast_ma=10, slow_ma=50)
        engine.set_strategy(strategy)
        
        engine.run_strategy()
        engine.print_results()
        
    else:
        print("无法获取数据，请检查API配置")


# ============== 示例 5: 组合策略 ==============
def example_multi_strategy():
    """多策略组合示例"""
    print("\n" + "=" * 50)
    print("示例 5: 多策略组合")
    print("=" * 50)
    
    # 为每个品种生成数据
    symbols = ["SPY", "GC", "SI"]
    
    for symbol in symbols:
        print(f"\n--- {symbol} ---")
        
        data = generate_sample_data(symbol, 365)
        engine = BacktestEngine(initial_capital=33000)  # 每策略3万
        
        engine.load_dataframe(data)
        
        if symbol == "SPY":
            strategy = CoveredCallStrategy(underlying="SPY")
        elif symbol == "GC":
            strategy = TrendFollowingStrategy(symbol="GC")
        else:
            strategy = MeanReversionStrategy(symbol="SI")
        
        engine.set_strategy(strategy)
        engine.run_strategy()
        engine.print_results()


# ============== 运行所有示例 ==============
if __name__ == "__main__":
    print("🚀 量化交易系统示例\n")
    
    # 运行各个示例
    # example_basic_backtest()
    # example_options_backtest()
    # example_gold_futures()
    # example_with_real_data()
    example_multi_strategy()
