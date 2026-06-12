import numpy as np
import pandas as pd

from agent.broker import PaperBroker
from agent.config import AgentConfig, RiskConfig
from agent.engine import TradingAgent
from agent.strategies import MovingAverageCross, Momentum, atr
from agent.data import synthetic_ohlcv


def _uptrend(days=120):
    idx = pd.bdate_range("2025-01-01", periods=days, name="date")
    close = pd.Series(np.linspace(100, 200, days), index=idx)
    return pd.DataFrame({"open": close, "high": close * 1.01,
                         "low": close * 0.99, "close": close, "volume": 1e6}, index=idx)


def test_ma_cross_goes_long_in_uptrend():
    hist = _uptrend()
    sig = MovingAverageCross(10, 30).evaluate("X", hist)
    assert sig.target == 1.0
    assert sig.stop_price is not None and sig.stop_price < hist["close"].iloc[-1]


def test_strategy_flat_during_warmup():
    hist = _uptrend(days=5)
    assert MovingAverageCross(10, 30).evaluate("X", hist).target == 0.0


def test_momentum_long_on_positive_return():
    hist = _uptrend()
    assert Momentum(lookback=60).evaluate("X", hist).target == 1.0


def test_atr_nonnegative():
    hist = synthetic_ohlcv(days=60, seed=3)
    a = atr(hist, 14)
    assert a > 0


def test_agent_paper_cycle_offline():
    """End-to-end paper cycle with an injected offline history provider."""
    hist = _uptrend()
    cfg = AgentConfig(symbols=["X"], initial_capital=100_000.0,
                      commission_per_share=0.0, slippage_bps=0.0,
                      risk=RiskConfig(target_annual_vol=None, max_position_fraction=0.2))
    agent = TradingAgent(cfg, MovingAverageCross(10, 30), PaperBroker(cfg),
                         history_provider=lambda s: hist)
    agent.run(max_cycles=1, sleep_fn=lambda s: None)
    pos = agent.broker.get_positions().get("X")
    assert pos is not None and pos.quantity > 0           # took the long
    # Position notional respects the 20% cap.
    assert pos.quantity * hist["close"].iloc[-1] <= 0.2 * 100_000 + 1
