import numpy as np
import pytest

from agent.config import AgentConfig, RiskConfig
from agent.data import synthetic_ohlcv
from agent.strategies import MovingAverageCross
from agent.validation import param_grid, walk_forward


def _cfg():
    return AgentConfig(symbols=["X"], initial_capital=100_000.0,
                       commission_per_share=0.0, slippage_bps=0.0,
                       risk=RiskConfig(target_annual_vol=None))


def test_param_grid_cartesian():
    g = param_grid(fast=[10, 20], slow=[50, 100])
    assert len(g) == 4
    assert {"fast": 10, "slow": 50} in g
    assert {"fast": 20, "slow": 100} in g


def test_walk_forward_runs_and_is_ordered():
    prices = synthetic_ohlcv(days=600, seed=11)
    grid = param_grid(fast=[10, 20], slow=[40, 60])
    res = walk_forward(_cfg(), MovingAverageCross, grid, "X", prices,
                       train=252, test=63)
    assert len(res.folds) >= 3
    assert res.oos_equity is not None and len(res.oos_equity) > 0
    m = res.oos_metrics
    for v in [m.total_return, m.cagr, m.sharpe, m.max_drawdown]:
        assert np.isfinite(v)
    # Out-of-sample windows are forward-ordered and non-overlapping.
    for a, b in zip(res.folds, res.folds[1:]):
        assert a.oos_start < b.oos_start
        assert a.is_start < a.oos_start <= a.oos_end


def test_walk_forward_selection_uses_only_grid_params():
    prices = synthetic_ohlcv(days=400, seed=5)
    grid = param_grid(fast=[5, 15], slow=[30])
    res = walk_forward(_cfg(), MovingAverageCross, grid, "X", prices)
    for fold in res.folds:
        assert fold.chosen_params in grid          # only ever picks from the grid


def test_walk_forward_too_short_raises():
    prices = synthetic_ohlcv(days=50, seed=1)
    with pytest.raises(ValueError):
        walk_forward(_cfg(), MovingAverageCross, param_grid(fast=[5], slow=[20]),
                     "X", prices, train=252, test=63)
