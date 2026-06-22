import numpy as np
import pandas as pd

from agent.broker import DryRunBroker, PaperBroker, make_broker, parse_instrument_ids, preflight
from agent.config import AgentConfig, RiskConfig
from agent.engine import TradingAgent
from agent.strategies import MovingAverageCross
from agent.types import Order, OrderType, Side


def test_parse_instrument_ids():
    assert parse_instrument_ids("AAPL:123,MSFT:456") == {"AAPL": "123", "MSFT": "456"}
    assert parse_instrument_ids("aapl:123") == {"AAPL": "123"}      # upper-cased
    assert parse_instrument_ids("") == {}
    assert parse_instrument_ids("garbage,,X:") == {}                # ignores junk


def test_dry_run_broker_sends_nothing():
    cfg = AgentConfig(initial_capital=100_000.0, slippage_bps=0.0)
    inner = PaperBroker(cfg)
    inner.update_price("X", 100.0)
    dry = DryRunBroker(inner)
    dry.update_price("X", 100.0)
    dry.submit_order(Order("X", Side.BUY, 100, OrderType.MARKET))
    assert len(dry.intended) == 1
    assert inner.get_positions() == {}                              # nothing actually traded
    assert abs(inner.get_account().equity - 100_000.0) < 1e-9


def test_make_broker_wraps_dry_run_offline():
    cfg = AgentConfig(live=False, dry_run=True)
    assert isinstance(make_broker(cfg), DryRunBroker)
    assert isinstance(make_broker(AgentConfig(live=False, dry_run=False)), PaperBroker)


def test_preflight_structure_and_credentials_flag():
    cfg = AgentConfig(live=False)
    cfg.webull_app_key = cfg.webull_app_secret = cfg.webull_account_id = ""
    rows = preflight(cfg)
    assert len(rows) >= 4 and all(len(r) == 3 for r in rows)
    creds = [ok for name, ok, _ in rows if name == "Credentials present"][0]
    assert creds is False                                           # none set


def test_engine_dry_run_opens_no_real_position():
    idx = pd.bdate_range("2025-01-01", periods=120, name="date")
    close = pd.Series(np.linspace(100, 200, 120), index=idx)
    hist = pd.DataFrame({"open": close, "high": close * 1.01,
                         "low": close * 0.99, "close": close, "volume": 1e6}, index=idx)
    cfg = AgentConfig(symbols=["X"], dry_run=True, slippage_bps=0.0,
                      risk=RiskConfig(target_annual_vol=None))
    broker = make_broker(cfg)                                       # DryRunBroker(PaperBroker)
    agent = TradingAgent(cfg, MovingAverageCross(10, 30), broker,
                         history_provider=lambda s: hist)
    agent.run(max_cycles=1, sleep_fn=lambda s: None)
    assert len(broker.intended) >= 1                               # it WANTED to buy
    assert broker.get_positions() == {}                            # but sent nothing
