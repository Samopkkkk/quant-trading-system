from agent.broker import PaperBroker
from agent.config import AgentConfig
from agent.types import Order, OrderType, Side


def _broker(**kw):
    cfg = AgentConfig(initial_capital=100_000.0, commission_per_share=0.0,
                      slippage_bps=0.0, **kw)
    return PaperBroker(cfg)


def test_buy_then_flatten():
    b = _broker()
    b.update_price("AAPL", 100.0)
    b.submit_order(Order("AAPL", Side.BUY, 100, OrderType.MARKET))
    assert b.get_positions()["AAPL"].quantity == 100
    assert abs(b.cash - 90_000.0) < 1e-6
    b.submit_order(Order("AAPL", Side.SELL, 100, OrderType.MARKET))
    assert "AAPL" not in b.get_positions()
    assert abs(b.cash - 100_000.0) < 1e-6


def test_slippage_and_commission_cost_money():
    cfg = AgentConfig(initial_capital=100_000.0, commission_per_share=0.01,
                      slippage_bps=10.0)
    b = PaperBroker(cfg)
    b.update_price("X", 100.0)
    b.submit_order(Order("X", Side.BUY, 100, OrderType.MARKET))
    # fill at 100 * (1 + 10bps) = 100.10, plus $1 commission
    assert abs(b.cash - (100_000.0 - 100 * 100.10 - 1.0)) < 1e-6


def test_short_position():
    b = _broker()
    b.update_price("X", 50.0)
    b.submit_order(Order("X", Side.SELL, 200, OrderType.MARKET))  # open short from flat
    pos = b.get_positions()["X"]
    assert pos.quantity == -200
    assert abs(b.cash - (100_000.0 + 200 * 50.0)) < 1e-6
    # equity unchanged right after (marked at fill price)
    assert abs(b.get_account().equity - 100_000.0) < 1e-6


def test_equity_tracks_marks():
    b = _broker()
    b.update_price("X", 100.0)
    b.submit_order(Order("X", Side.BUY, 100, OrderType.MARKET))
    b.update_price("X", 110.0)
    assert abs(b.get_account().equity - 101_000.0) < 1e-6  # +$10 * 100 shares
