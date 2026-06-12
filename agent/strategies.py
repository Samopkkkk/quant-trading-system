"""Trading strategies.

A strategy turns price history into a desired exposure (a `Signal`). It never
sees the current (still-forming) bar: `history` contains only CLOSED bars, and
the returned target applies to the NEXT bar. This is what prevents look-ahead
bias, the single most common way backtests lie.

Strategies decide *direction and conviction*; the RiskManager decides *size*.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from .types import Signal


def atr(history: pd.DataFrame, period: int = 14) -> float:
    """Average True Range of the most recent `period` closed bars."""
    if len(history) < period + 1:
        return float("nan")
    high, low, close = history["high"], history["low"], history["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return float(tr.tail(period).mean())


class Strategy(ABC):
    """Base class for all strategies."""

    #: Minimum number of closed bars required before a non-flat signal is valid.
    warmup: int = 1

    @abstractmethod
    def evaluate(self, symbol: str, history: pd.DataFrame) -> Signal:
        """Return desired exposure for the next bar given CLOSED bars only."""

    def _flat(self, symbol: str, reason: str = "warming up") -> Signal:
        return Signal(symbol=symbol, target=0.0, reason=reason)


class MovingAverageCross(Strategy):
    """Long when the fast SMA is above the slow SMA; optionally short below."""

    def __init__(self, fast: int = 20, slow: int = 50, allow_short: bool = False,
                 atr_stop_mult: float = 3.0):
        if fast >= slow:
            raise ValueError("fast period must be < slow period")
        self.fast, self.slow = fast, slow
        self.allow_short = allow_short
        self.atr_stop_mult = atr_stop_mult
        self.warmup = slow + 1

    def evaluate(self, symbol: str, history: pd.DataFrame) -> Signal:
        if len(history) < self.warmup:
            return self._flat(symbol)
        close = history["close"]
        fast_ma = close.tail(self.fast).mean()
        slow_ma = close.tail(self.slow).mean()
        last = float(close.iloc[-1])
        a = atr(history, self.fast)

        if fast_ma > slow_ma:
            stop = last - self.atr_stop_mult * a if a == a else None  # a==a guards NaN
            return Signal(symbol, target=1.0, stop_price=stop, reason="fast>slow")
        if self.allow_short and fast_ma < slow_ma:
            stop = last + self.atr_stop_mult * a if a == a else None
            return Signal(symbol, target=-1.0, stop_price=stop, reason="fast<slow")
        return Signal(symbol, target=0.0, reason="no trend")


class Momentum(Strategy):
    """Time-series momentum: go long after positive trailing return, else flat."""

    def __init__(self, lookback: int = 90, threshold: float = 0.0,
                 allow_short: bool = False, atr_stop_mult: float = 3.0):
        self.lookback = lookback
        self.threshold = threshold
        self.allow_short = allow_short
        self.atr_stop_mult = atr_stop_mult
        self.warmup = lookback + 1

    def evaluate(self, symbol: str, history: pd.DataFrame) -> Signal:
        if len(history) < self.warmup:
            return self._flat(symbol)
        close = history["close"]
        ret = float(close.iloc[-1] / close.iloc[-self.lookback - 1] - 1.0)
        last = float(close.iloc[-1])
        a = atr(history)

        if ret > self.threshold:
            stop = last - self.atr_stop_mult * a if a == a else None
            return Signal(symbol, target=1.0, stop_price=stop, reason=f"mom={ret:.3f}")
        if self.allow_short and ret < -self.threshold:
            stop = last + self.atr_stop_mult * a if a == a else None
            return Signal(symbol, target=-1.0, stop_price=stop, reason=f"mom={ret:.3f}")
        return Signal(symbol, target=0.0, reason=f"mom={ret:.3f}")


class RsiMeanReversion(Strategy):
    """Buy oversold (RSI < lower), exit/short overbought (RSI > upper)."""

    def __init__(self, period: int = 14, lower: float = 30.0, upper: float = 70.0,
                 allow_short: bool = False):
        self.period = period
        self.lower, self.upper = lower, upper
        self.allow_short = allow_short
        self.warmup = period + 1

    @staticmethod
    def _rsi(close: pd.Series, period: int) -> float:
        delta = close.diff().dropna()
        gain = delta.clip(lower=0).tail(period).mean()
        loss = (-delta.clip(upper=0)).tail(period).mean()
        if loss == 0:
            return 100.0
        rs = gain / loss
        return float(100.0 - 100.0 / (1.0 + rs))

    def evaluate(self, symbol: str, history: pd.DataFrame) -> Signal:
        if len(history) < self.warmup:
            return self._flat(symbol)
        rsi = self._rsi(history["close"], self.period)
        if rsi < self.lower:
            return Signal(symbol, target=1.0, reason=f"rsi={rsi:.1f} oversold")
        if rsi > self.upper:
            return Signal(symbol, target=(-1.0 if self.allow_short else 0.0),
                          reason=f"rsi={rsi:.1f} overbought")
        return Signal(symbol, target=0.0, reason=f"rsi={rsi:.1f}")


# Registry for the CLI.
STRATEGIES: dict[str, type[Strategy]] = {
    "ma_cross": MovingAverageCross,
    "momentum": Momentum,
    "rsi": RsiMeanReversion,
}
