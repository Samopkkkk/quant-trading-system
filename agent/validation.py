"""Walk-forward validation — the antidote to overfitting.

A single backtest over all history is the easiest way to fool yourself: you can
always find parameters that fit the past. Walk-forward validation instead:

    1. Selects parameters on an IN-SAMPLE window.
    2. Measures performance on the next, unseen OUT-OF-SAMPLE window.
    3. Rolls forward and repeats, then stitches the out-of-sample pieces.

The stitched out-of-sample curve is a far more honest estimate of how a strategy
would have actually performed, because every trade in it was made with parameters
chosen *before* that data was seen. Parameter selection never touches the
out-of-sample window, so there is no look-ahead across folds.

It is still not a prediction. A robust walk-forward result lowers (does not
eliminate) the chance that an edge is a mirage.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from .backtest import Backtester, Metrics, compute_metrics
from .config import AgentConfig
from .strategies import Strategy

StrategyFactory = Callable[..., Strategy]


def param_grid(**axes) -> list[dict]:
    """Cartesian product of keyword lists into a list of param dicts.

    >>> param_grid(fast=[10, 20], slow=[50])
    [{'fast': 10, 'slow': 50}, {'fast': 20, 'slow': 50}]
    """
    keys = list(axes)
    return [dict(zip(keys, combo)) for combo in itertools.product(*axes.values())]


@dataclass
class Fold:
    index: int
    is_start: pd.Timestamp
    oos_start: pd.Timestamp
    oos_end: pd.Timestamp
    chosen_params: dict
    is_score: float
    oos_metrics: Metrics


@dataclass
class WalkForwardResult:
    folds: list[Fold] = field(default_factory=list)
    oos_equity: pd.Series | None = None
    oos_metrics: Metrics = field(default_factory=Metrics)

    def summary(self) -> str:
        lines = [
            "================ Walk-Forward (out-of-sample) ================",
            f"  Folds            : {len(self.folds)}",
            f"  OOS total return : {self.oos_metrics.total_return * 100:,.2f}%",
            f"  OOS CAGR         : {self.oos_metrics.cagr * 100:,.2f}%",
            f"  OOS Sharpe       : {self.oos_metrics.sharpe:,.2f}",
            f"  OOS max drawdown : {self.oos_metrics.max_drawdown * 100:,.2f}%",
            f"  OOS final equity : ${self.oos_metrics.final_equity:,.2f}",
            "  Per-fold chosen params (in-sample score -> OOS return):",
        ]
        for f in self.folds:
            lines.append(
                f"    [{f.index}] {f.chosen_params}  "
                f"is={f.is_score:.2f} -> oos={f.oos_metrics.total_return * 100:+.1f}%"
            )
        lines.append("=============================================================")
        return "\n".join(lines)


def walk_forward(
    config: AgentConfig,
    strategy_factory: StrategyFactory,
    grid: list[dict],
    symbol: str,
    prices: pd.DataFrame,
    train: int = 252,
    test: int = 63,
    select_metric: str = "sharpe",
    periods_per_year: int = 252,
) -> WalkForwardResult:
    """Roll a train/test window across `prices`, selecting params in-sample only."""
    prices = prices.sort_index()
    n = len(prices)
    if n < train + 2:
        raise ValueError(f"need at least {train + 2} bars, got {n}")

    result = WalkForwardResult()
    oos_return_pieces: list[pd.Series] = []
    i = 0
    fold_idx = 0
    while i + train + 1 <= n:
        oos_end_pos = min(i + train + test, n)
        is_slice = prices.iloc[i:i + train]
        full_slice = prices.iloc[i:oos_end_pos]            # in-sample + OOS (for warmup)
        oos_start_ts = prices.index[i + train]

        # 1) Select parameters using ONLY the in-sample slice.
        best_score, best_params = -np.inf, grid[0]
        for params in grid:
            rep = Backtester(config, strategy_factory(**params),
                             periods_per_year=periods_per_year).run(symbol, is_slice)
            score = float(getattr(rep.metrics, select_metric))
            if np.isfinite(score) and score > best_score:
                best_score, best_params = score, params

        # 2) Evaluate the chosen params over the full slice; score the OOS part only.
        rep_full = Backtester(config, strategy_factory(**best_params),
                              periods_per_year=periods_per_year).run(symbol, full_slice)
        oos_equity = rep_full.equity_curve.loc[oos_start_ts:]
        oos_ret = oos_equity.pct_change().dropna()
        oos_return_pieces.append(oos_ret)

        result.folds.append(Fold(
            index=fold_idx, is_start=prices.index[i], oos_start=oos_start_ts,
            oos_end=prices.index[oos_end_pos - 1], chosen_params=best_params,
            is_score=best_score if np.isfinite(best_score) else 0.0,
            oos_metrics=compute_metrics(oos_equity, [], periods_per_year),
        ))
        fold_idx += 1
        i += test                                          # roll forward (non-overlapping OOS)

    # 3) Stitch the out-of-sample return pieces into one equity curve.
    if oos_return_pieces:
        stitched_ret = pd.concat(oos_return_pieces)
        stitched_eq = (1.0 + stitched_ret).cumprod() * config.initial_capital
        result.oos_equity = stitched_eq
        result.oos_metrics = compute_metrics(stitched_eq, [], periods_per_year)
    return result
