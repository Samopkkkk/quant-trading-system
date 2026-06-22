from collections import defaultdict

import numpy as np
import pandas as pd

from agent.backtest import PortfolioBacktester, align_prices, realized_pnls_multi
from agent.config import AgentConfig, RiskConfig
from agent.data import synthetic_ohlcv
from agent.strategies import MovingAverageCross
from agent.types import Fill, Order, OrderType, Side


def _uptrend(days, start, slope, idx):
    close = pd.Series(np.linspace(start, start + slope, days), index=idx)
    return pd.DataFrame({"open": close, "high": close * 1.01,
                         "low": close * 0.99, "close": close, "volume": 1e6}, index=idx)


def _net_gross(fills, last_px):
    pos = defaultdict(float)
    for f in fills:
        q = f.filled_quantity if f.order.side == Side.BUY else -f.filled_quantity
        pos[f.order.symbol] += q
    return sum(abs(q) * last_px[s] for s, q in pos.items())


def test_align_prices_intersects_dates():
    idx = pd.bdate_range("2025-01-01", periods=10, name="date")
    a = synthetic_ohlcv(days=10, seed=1, start=idx[0])
    a.index = idx
    b = a.iloc[2:]                       # shorter history
    common, aligned = align_prices({"A": a, "B": b})
    assert len(common) == 8
    assert all(len(df) == 8 for df in aligned.values())


def test_portfolio_runs_and_is_deterministic():
    syms = ["A", "B", "C"]
    prices = {s: synthetic_ohlcv(days=300, seed=i + 1) for i, s in enumerate(syms)}
    cfg = AgentConfig(symbols=syms, initial_capital=100_000.0, slippage_bps=0.0,
                      risk=RiskConfig(target_annual_vol=None))
    r1 = PortfolioBacktester(cfg, MovingAverageCross(10, 30)).run(prices)
    r2 = PortfolioBacktester(cfg, MovingAverageCross(10, 30)).run(prices)
    assert len(r1.equity_curve) == 300
    assert r1.metrics.final_equity == r2.metrics.final_equity
    assert r1.metrics.final_equity > 0


def test_leverage_cap_binds_across_book():
    idx = pd.bdate_range("2025-01-01", periods=120, name="date")
    # Three strongly trending symbols: each strategy wants a full long.
    prices = {"A": _uptrend(120, 100, 100, idx),
              "B": _uptrend(120, 50, 60, idx),
              "C": _uptrend(120, 200, 150, idx)}
    last_px = {s: float(df["close"].iloc[-1]) for s, df in prices.items()}

    # Each position capped at 50% of equity => 3 symbols would be 1.5x gross.
    # risk_per_trade_fraction=1.0 disables the per-trade stop cap so the
    # *leverage* cap is the binding constraint we want to test here.
    risk_capped = RiskConfig(target_annual_vol=None, max_position_fraction=0.5,
                             max_gross_leverage=1.0, risk_per_trade_fraction=1.0)
    risk_loose = RiskConfig(target_annual_vol=None, max_position_fraction=0.5,
                            max_gross_leverage=3.0, risk_per_trade_fraction=1.0)
    cfg_c = AgentConfig(symbols=list(prices), slippage_bps=0.0, risk=risk_capped)
    cfg_l = AgentConfig(symbols=list(prices), slippage_bps=0.0, risk=risk_loose)

    rc = PortfolioBacktester(cfg_c, MovingAverageCross(10, 30)).run(prices)
    rl = PortfolioBacktester(cfg_l, MovingAverageCross(10, 30)).run(prices)

    gross_c = _net_gross(rc.fills, last_px)
    gross_l = _net_gross(rl.fills, last_px)
    # The 1.0x cap holds gross well below the loose 3.0x book.
    assert gross_c < gross_l
    assert gross_c <= 1.2 * rc.metrics.final_equity        # ~1.0x, not 1.5x


def test_realized_pnls_multi_groups_by_symbol():
    def fill(sym, side, qty, px):
        return Fill(Order(sym, side, qty, OrderType.MARKET), px, qty, 0.0,
                    pd.Timestamp.now("UTC"))
    fills = [fill("A", Side.BUY, 10, 100), fill("B", Side.BUY, 10, 50),
             fill("A", Side.SELL, 10, 110), fill("B", Side.SELL, 10, 45)]
    pnls = sorted(realized_pnls_multi(fills))
    assert pnls == [-50.0, 100.0]                          # A:+100, B:-50, grouped
