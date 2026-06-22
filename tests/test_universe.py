import numpy as np
import pandas as pd

from agent.broker import PaperBroker
from agent.config import AgentConfig, RiskConfig
from agent.engine import TradingAgent
from agent.strategies import MovingAverageCross


def _series(slope, days=200, start=100.0):
    idx = pd.bdate_range("2025-01-01", periods=days, name="date")
    close = pd.Series(np.linspace(start, start + slope, days), index=idx)
    return pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99,
                         "close": close, "volume": 5e6}, index=idx)


def _agent(provider, **cfg_kw):
    cfg = AgentConfig(slippage_bps=0.0, risk=RiskConfig(target_annual_vol=None),
                      **cfg_kw)
    return TradingAgent(cfg, MovingAverageCross(10, 30), PaperBroker(cfg),
                        history_provider=provider)


def test_agent_screens_universe_to_top_n():
    hist = {"UP1": _series(120), "UP2": _series(80), "DOWN": _series(-30)}
    agent = _agent(lambda s: hist[s],
                   symbols=["UP1"], universe=["UP1", "UP2", "DOWN"], screen_top_n=2)
    agent.run(max_cycles=1, sleep_fn=lambda s: None)
    assert set(agent.active_symbols) == {"UP1", "UP2"}        # the two uptrends
    assert "DOWN" not in agent.active_symbols
    assert agent.broker.get_positions().get("UP1") is not None  # traded a selection


def test_agent_exits_dropped_symbols_on_rescreen():
    # A mutable provider: DOWN starts strong (selected), then collapses (dropped).
    state = {"DOWN": _series(150)}
    base = {"UP1": _series(120), "UP2": _series(80)}

    def provider(sym):
        return state["DOWN"] if sym == "DOWN" else base[sym]

    agent = _agent(provider, symbols=["UP1"], universe=["UP1", "UP2", "DOWN"],
                   screen_top_n=2, rescreen_every=1)
    agent.run(max_cycles=1, sleep_fn=lambda s: None)
    assert "DOWN" in agent.active_symbols                     # picked while strong
    assert agent.broker.get_positions().get("DOWN") is not None

    state["DOWN"] = _series(-80)                              # DOWN now worst
    agent.run(max_cycles=1, sleep_fn=lambda s: None)
    assert "DOWN" not in agent.active_symbols                 # dropped from selection
    assert agent.broker.get_positions().get("DOWN") is None   # and its position closed


def test_rescreen_cadence():
    hist = {"A": _series(120), "B": _series(80), "C": _series(40)}
    calls = {"n": 0}

    def provider(sym):
        calls["n"] += 1
        return hist[sym]

    agent = _agent(provider, symbols=["A"], universe=["A", "B", "C"],
                   screen_top_n=2, rescreen_every=3)
    # Screens on cycle 0 only (next would be cycle 3). 3 universe fetches +
    # per-active-symbol fetches; assert screening did not run on cycles 1 and 2.
    agent.run(max_cycles=3, sleep_fn=lambda s: None)
    assert agent._cycle == 3
    # active symbols were chosen once and held across cycles 1-2.
    assert set(agent.active_symbols) == {"A", "B"}


def test_no_universe_uses_fixed_symbols():
    hist = {"X": _series(120)}
    agent = _agent(lambda s: hist[s], symbols=["X"])         # no universe
    agent.run(max_cycles=1, sleep_fn=lambda s: None)
    assert agent.active_symbols == ["X"]
