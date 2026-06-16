"""Money-flow and liquidity indicators (资金流向指标).

All are computed from OHLCV bars — the data we actually have. They proxy "capital
flow" via where price closes within each bar's range, weighted by volume:

  * chaikin_money_flow (CMF): buying vs selling pressure, range [-1, 1].
  * money_flow_index (MFI):   volume-weighted RSI, range [0, 100].
  * obv_series (OBV):         cumulative up/down volume.
  * average_dollar_volume:    liquidity (close * volume).

NOTE: true "main-force" order-flow (大单/主力资金) needs tick or level-2 data, which
this system cannot obtain from OHLCV. If a broker money-flow feed becomes
available, add it as another signal source; these indicators are the honest
OHLCV-only approximation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def chaikin_money_flow(history: pd.DataFrame, period: int = 20) -> float:
    """CMF over the last `period` bars. >0 = net inflow, <0 = net outflow."""
    if len(history) < period:
        return float("nan")
    h, l, c, v = (history["high"], history["low"], history["close"], history["volume"])
    rng = (h - l).replace(0, np.nan)
    mfm = (((c - l) - (h - c)) / rng).fillna(0.0)        # money-flow multiplier
    mfv = mfm * v                                         # money-flow volume
    vol_sum = float(v.tail(period).sum())
    if vol_sum == 0:
        return float("nan")
    return float(mfv.tail(period).sum() / vol_sum)


def money_flow_index(history: pd.DataFrame, period: int = 14) -> float:
    """MFI over the last `period` bars. >80 overbought, <20 oversold."""
    if len(history) < period + 1:
        return float("nan")
    tp = (history["high"] + history["low"] + history["close"]) / 3.0
    rmf = tp * history["volume"]                          # raw money flow
    delta = tp.diff()
    pos = rmf.where(delta > 0, 0.0).tail(period).sum()
    neg = rmf.where(delta < 0, 0.0).tail(period).sum()
    if neg == 0:
        return 100.0
    ratio = pos / neg
    return float(100.0 - 100.0 / (1.0 + ratio))


def obv_series(history: pd.DataFrame) -> pd.Series:
    """On-Balance Volume as a cumulative series (its slope is the signal)."""
    direction = np.sign(history["close"].diff().fillna(0.0))
    return (direction * history["volume"]).cumsum()


def average_dollar_volume(history: pd.DataFrame, window: int = 20) -> float:
    """Mean traded notional (close * volume) over `window` bars — a liquidity proxy."""
    if len(history) == 0:
        return 0.0
    return float((history["close"] * history["volume"]).tail(window).mean())
