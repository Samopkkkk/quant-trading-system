from datetime import datetime

import numpy as np
import pandas as pd

from agent.config import AgentConfig, RiskConfig
from agent.engine import TradingAgent
from agent.broker import PaperBroker
from agent.marketclock import ET, is_market_open, is_trading_day
from agent.strategies import MovingAverageCross


def et(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=ET)


def test_open_during_weekday_rth():
    assert is_market_open(et(2026, 6, 15, 10, 0))      # Monday 10:00 ET
    assert is_market_open(et(2026, 6, 15, 9, 30))      # exactly at the open


def test_closed_outside_rth():
    assert not is_market_open(et(2026, 6, 15, 9, 29))  # pre-market
    assert not is_market_open(et(2026, 6, 15, 16, 0))  # close is exclusive
    assert not is_market_open(et(2026, 6, 15, 18, 0))  # after-hours


def test_closed_on_weekend_and_holiday():
    assert not is_market_open(et(2026, 6, 14, 12, 0))  # Sunday
    assert not is_market_open(et(2026, 6, 13, 12, 0))  # Saturday
    assert not is_market_open(et(2026, 7, 3, 12, 0))   # July 4th observed (Fri)
    assert not is_trading_day(et(2026, 12, 25, 12, 0).date())  # Christmas


def test_naive_datetime_assumed_et():
    assert is_market_open(datetime(2026, 6, 15, 10, 0))   # naive -> treated as ET


def _uptrend(days=120):
    idx = pd.bdate_range("2025-01-01", periods=days, name="date")
    close = pd.Series(np.linspace(100, 200, days), index=idx)
    return pd.DataFrame({"open": close, "high": close * 1.01,
                         "low": close * 0.99, "close": close, "volume": 1e6}, index=idx)


def _agent(clock_dt, enforce):
    hist = _uptrend()
    cfg = AgentConfig(symbols=["X"], slippage_bps=0.0, enforce_market_hours=enforce,
                      risk=RiskConfig(target_annual_vol=None))
    return TradingAgent(cfg, MovingAverageCross(10, 30), PaperBroker(cfg),
                        history_provider=lambda s: hist, clock=lambda: clock_dt)


def test_engine_skips_when_market_closed():
    agent = _agent(et(2026, 6, 14, 12, 0), enforce=True)   # Sunday
    agent.run(max_cycles=1, sleep_fn=lambda s: None)
    assert agent.broker.get_positions() == {}              # did nothing


def test_engine_trades_when_open():
    agent = _agent(et(2026, 6, 15, 10, 0), enforce=True)   # Monday RTH
    agent.run(max_cycles=1, sleep_fn=lambda s: None)
    assert agent.broker.get_positions().get("X") is not None
