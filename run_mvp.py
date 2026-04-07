"""
MVP Runner - Single Strategy Backtest
=====================================
This is the minimal working example for the quant trading system.
Only ONE strategy is implemented here to keep it simple and testable.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest.engine import BacktestEngine
from strategies.futures_strategies import TrendFollowingStrategy


def generate_test_data(symbol: str = "SPY", days: int = 252) -> pd.DataFrame:
    """
    Generate realistic test data with trends and oscillations.
    
    Args:
        symbol: Asset symbol
        days: Number of trading days
    
    Returns:
        DataFrame with OHLCV data
    """
    # Generate dates (weekdays only)
    dates = pd.date_range(end=datetime.now(), periods=days, freq='B')
    
    np.random.seed(42)  # Reproducible
    
    # Generate realistic price data with moderate trend
    # Using small daily returns that compound reasonably
    daily_return = 0.0005  # ~12% annual return
    volatility = 0.015  # ~15% annual volatility
    
    trend = daily_return  # Constant drift
    noise = np.random.randn(days) * volatility
    
    returns = trend + noise
    price = 100 * np.cumprod(1 + returns)
    price = np.insert(price, 0, 100)  # Start at 100
    price = price[:-1]  # Remove last extra element
    
    # Generate OHLC
    data = pd.DataFrame({
        'date': dates,
        'open': price * (1 + np.random.uniform(-0.01, 0.01, days)),
        'high': price * (1 + np.abs(np.random.uniform(0, 0.02, days))),
        'low': price * (1 - np.abs(np.random.uniform(0, 0.02, days))),
        'close': price,
        'volume': np.random.randint(1_000_000, 10_000_000, days)
    })
    
    data.set_index('date', inplace=True)
    return data


def run_mvp_backtest():
    """
    Run the MVP backtest with TrendFollowingStrategy.
    
    This demonstrates a complete research-to-backtest loop:
    1. Generate/load data
    2. Configure strategy
    3. Run backtest
    4. Review results
    """
    print("=" * 60)
    print("MVP Backtest - Trend Following Strategy")
    print("=" * 60)
    
    # Step 1: Prepare data
    print("\n[1] Loading data...")
    data = generate_test_data("SPY", days=252)
    print(f"    Generated {len(data)} days of test data")
    print(f"    Date range: {data.index[0].date()} to {data.index[-1].date()}")
    print(f"    Price range: ${data['close'].min():.2f} - ${data['close'].max():.2f}")
    
    # Step 2: Initialize engine
    print("\n[2] Initializing backtest engine...")
    engine = BacktestEngine(initial_capital=100_000)
    engine.load_dataframe(data)
    print(f"    Initial capital: ${engine.initial_capital:,.2f}")
    
    # Step 3: Configure strategy
    print("\n[3] Configuring strategy...")
    strategy = TrendFollowingStrategy(
        symbol="SPY",
        fast_ma=10,   # Fast moving average period
        slow_ma=50    # Slow moving average period
    )
    engine.set_strategy(strategy)
    print(f"    Strategy: {strategy.name}")
    print(f"    Parameters: fast_ma={strategy.fast_ma}, slow_ma={strategy.slow_ma}")
    
    # Step 4: Run backtest
    print("\n[4] Running backtest...")
    engine.run_strategy()
    print(f"    Completed!")
    
    # Step 5: Review results
    print("\n[5] Results:")
    result = engine.get_results()
    
    print(f"    Total trades: {result.total_trades}")
    print(f"    Winning trades: {result.winning_trades}")
    print(f"    Losing trades: {result.losing_trades}")
    print(f"    Win rate: {result.win_rate:.1%}")
    print(f"    Total P&L: ${result.total_pnl:,.2f}")
    print(f"    Total commission: ${result.total_commission:,.2f}")
    print(f"    Max drawdown: {result.max_drawdown:.1%}")
    print(f"    Sharpe ratio: {result.sharpe_ratio:.2f}")
    print(f"    Final equity: ${engine.equity_curve[-1]:,.2f}")
    
    # Step 6: Show trades
    if engine.trades:
        print("\n[6] Trade history:")
        for trade in engine.trades[:10]:  # Show first 10
            print(f"    {trade.date} {trade.action.upper():4s} {trade.symbol:4s} "
                  f"qty={trade.quantity} @ ${trade.price:.2f} "
                  f"pnl=${trade.pnl:+.2f}")
        if len(engine.trades) > 10:
            print(f"    ... and {len(engine.trades) - 10} more trades")
    
    print("\n" + "=" * 60)
    print("Backtest completed successfully!")
    print("=" * 60)
    
    return engine, result


if __name__ == "__main__":
    run_mvp_backtest()
