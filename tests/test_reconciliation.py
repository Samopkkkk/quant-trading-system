from datetime import datetime

import numpy as np
import pandas as pd

from agent.broker import Broker
from agent.config import AgentConfig, RiskConfig
from agent.engine import TradingAgent, _order_is_terminal
from agent.strategies import MovingAverageCross
from agent.types import AccountSnapshot, Fill, OrderStatus, Position


class FakeAsyncBroker(Broker):
    """Broker whose orders stay PENDING until `status` is changed (like a real
    venue). Positions are not auto-updated, so the agent keeps wanting to trade —
    which is exactly what the in-flight guard must suppress."""

    def __init__(self):
        self.submitted = []
        self.status = "PENDING"
        self._n = 0

    def get_account(self):
        return AccountSnapshot(cash=100_000.0, equity=100_000.0, positions={})

    def get_positions(self):
        return {}

    def update_price(self, symbol, price):
        pass

    def submit_order(self, order):
        self._n += 1
        self.submitted.append(order)
        return Fill(order, 0.0, 0.0, 0.0, datetime.utcnow(),
                    status=OrderStatus.PENDING, broker_order_id=f"oid{self._n}")

    def cancel_order(self, broker_order_id):
        return True

    def get_order_status(self, client_order_id):
        return {"status": self.status}


def _uptrend(days=120):
    idx = pd.bdate_range("2025-01-01", periods=days, name="date")
    close = pd.Series(np.linspace(100, 200, days), index=idx)
    return pd.DataFrame({"open": close, "high": close * 1.01,
                         "low": close * 0.99, "close": close, "volume": 1e6}, index=idx)


def _agent(broker):
    cfg = AgentConfig(symbols=["X"], risk=RiskConfig(target_annual_vol=None))
    return TradingAgent(cfg, MovingAverageCross(10, 30), broker,
                        history_provider=lambda s: _uptrend())


def test_order_is_terminal_parsing():
    assert _order_is_terminal({"status": "FILLED"})
    assert _order_is_terminal({"data": {"order_status": "Cancelled"}})
    assert not _order_is_terminal({"status": "PENDING"})
    assert not _order_is_terminal({"weird": "shape"})


def test_inflight_guard_prevents_duplicate_orders():
    b = FakeAsyncBroker()
    agent = _agent(b)
    agent.run(max_cycles=3, sleep_fn=lambda s: None)        # order stays PENDING
    assert len(b.submitted) == 1                            # not stacked 3x


def test_terminal_status_releases_guard():
    b = FakeAsyncBroker()
    agent = _agent(b)
    agent.run(max_cycles=1, sleep_fn=lambda s: None)
    assert len(b.submitted) == 1
    b.status = "FILLED"                                     # the order completes
    agent.run(max_cycles=1, sleep_fn=lambda s: None)        # reconcile clears it
    assert len(b.submitted) == 2                            # free to act again


def test_ttl_clears_a_stuck_order():
    b = FakeAsyncBroker()                                   # never goes terminal
    agent = _agent(b)
    agent.max_inflight_cycles = 2
    agent.run(max_cycles=4, sleep_fn=lambda s: None)
    # cycle1 submit; cycles 2-3 guarded; cycle4 TTL clears -> submit again
    assert len(b.submitted) == 2
