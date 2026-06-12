import pandas as pd

from agent.backtest import Backtester, compute_metrics, realized_pnls_from_fills
from agent.config import AgentConfig, RiskConfig
from agent.data import synthetic_ohlcv
from agent.strategies import MovingAverageCross, Strategy
from agent.types import Signal


class _Spy(Strategy):
    """Records the history it is shown so we can prove there is no look-ahead."""
    warmup = 1

    def __init__(self):
        self.seen_last_ts = []

    def evaluate(self, symbol, history):
        self.seen_last_ts.append(history.index[-1])
        return Signal(symbol, 0.0)


def _cfg():
    return AgentConfig(symbols=["X"], initial_capital=100_000.0,
                       commission_per_share=0.0, slippage_bps=0.0,
                       risk=RiskConfig(target_annual_vol=None))


def test_no_lookahead_strategy_only_sees_closed_bars():
    prices = synthetic_ohlcv(days=30, seed=1)
    spy = _Spy()
    Backtester(_cfg(), spy).run("X", prices)
    # The k-th evaluate() (k=0..) decides the order for bar t=k+1, and must only
    # see bars up to index t-1 = prices.index[k].
    assert len(spy.seen_last_ts) == len(prices) - 1
    for k, ts in enumerate(spy.seen_last_ts):
        assert ts == prices.index[k]                 # last closed bar is strictly earlier
        assert ts < prices.index[k + 1]              # than the bar being traded


def test_backtest_runs_and_is_deterministic():
    prices = synthetic_ohlcv(days=252, seed=7)
    r1 = Backtester(_cfg(), MovingAverageCross(10, 30)).run("X", prices)
    r2 = Backtester(_cfg(), MovingAverageCross(10, 30)).run("X", prices)
    assert len(r1.equity_curve) == len(prices)
    assert r1.metrics.final_equity == r2.metrics.final_equity     # deterministic
    assert r1.metrics.final_equity > 0
    # Sanity: all metric fields are finite numbers.
    m = r1.metrics
    for v in [m.total_return, m.cagr, m.annual_vol, m.sharpe, m.max_drawdown]:
        assert v == v and abs(v) < 1e6


def test_metrics_on_known_curve():
    # Monotonic +1%/day for 252 days -> total return ~ (1.01^252 - 1)
    idx = pd.bdate_range("2025-01-01", periods=253, name="date")
    eq = pd.Series([100_000 * (1.01 ** i) for i in range(253)], index=idx)
    m = compute_metrics(eq, realized=[], periods_per_year=252)
    assert abs(m.total_return - (1.01 ** 252 - 1)) < 1e-6
    assert m.max_drawdown == 0.0                      # never declines
    assert m.sharpe > 0


def test_profit_factor_from_realized():
    from agent.types import Order, Side, OrderType, Fill
    from datetime import datetime

    def fill(side, qty, px):
        return Fill(Order("X", side, qty, OrderType.MARKET), px, qty, 0.0, datetime.utcnow())

    # buy 100@100, sell 100@110 (win +1000); buy 100@110, sell 100@105 (loss -500)
    fills = [fill(Side.BUY, 100, 100), fill(Side.SELL, 100, 110),
             fill(Side.BUY, 100, 110), fill(Side.SELL, 100, 105)]
    pnls = realized_pnls_from_fills(fills)
    assert pnls == [1000.0, -500.0]
    m = compute_metrics(pd.Series([1, 2], index=pd.bdate_range("2025-01-01", periods=2)), pnls)
    assert m.num_trades == 2
    assert abs(m.win_rate - 0.5) < 1e-9
    assert abs(m.profit_factor - 2.0) < 1e-9          # 1000 / 500
