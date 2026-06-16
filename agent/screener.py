"""Symbol/universe selection (新标的选择).

Rather than trade a fixed hard-coded list, screen a candidate universe and pick
the names worth trading. A symbol must first be liquid enough to trade, then it
is ranked by a composite of trend (momentum) and money flow (CMF) — so selection
uses the same 资金流向 signal as the strategy layer.

`screen_universe` returns the ranked, filtered results; `select_symbols` is the
convenience that returns just the top-N tickers.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .indicators import average_dollar_volume, chaikin_money_flow


@dataclass
class ScreenResult:
    symbol: str
    score: float
    dollar_volume: float
    momentum: float
    cmf: float


def _momentum(history: pd.DataFrame, lookback: int) -> float:
    if len(history) < lookback + 1:
        return 0.0
    return float(history["close"].iloc[-1] / history["close"].iloc[-lookback - 1] - 1.0)


def screen_universe(
    histories: dict[str, pd.DataFrame],
    momentum_lookback: int = 90,
    cmf_period: int = 20,
    min_dollar_volume: float = 1e7,
    min_history: int = 120,
    min_cmf: float | None = None,
) -> list[ScreenResult]:
    """Filter for liquidity/history, then rank by momentum + money flow (desc).

    If `min_cmf` is set, also require net capital inflow (CMF >= min_cmf) — i.e.
    only select symbols money is actually flowing INTO (资金流向 applied to 选股).
    """
    results: list[ScreenResult] = []
    for symbol, df in histories.items():
        if df is None or len(df) < min_history:
            continue                                          # not enough history
        adv = average_dollar_volume(df)
        if adv < min_dollar_volume:
            continue                                          # too illiquid to trade
        mom = _momentum(df, momentum_lookback)
        cmf = chaikin_money_flow(df, cmf_period)
        cmf = 0.0 if cmf != cmf else cmf                      # NaN -> neutral
        if min_cmf is not None and cmf < min_cmf:
            continue                                          # money flowing out -> skip
        results.append(ScreenResult(symbol, mom + cmf, adv, mom, cmf))
    results.sort(key=lambda r: r.score, reverse=True)
    return results


def select_symbols(histories: dict[str, pd.DataFrame], top_n: int = 5,
                   **kwargs) -> list[str]:
    """Top-N tickers by the screen score."""
    return [r.symbol for r in screen_universe(histories, **kwargs)[:top_n]]
