"""Risk management: the part that keeps an aggressive strategy from becoming a
total loss.

The RiskManager does two jobs:
  1. SIZING - turn a strategy's [-1, 1] intent into an actual share quantity,
     respecting per-position caps, per-trade stop risk, and volatility targeting.
  2. CIRCUIT BREAKERS - a daily-loss halt (stop opening new risk) and a
     max-drawdown kill switch (flatten and stop). These are non-negotiable and
     enforced regardless of what any strategy wants to do.

There is no sizing scheme that produces a *guaranteed* return. Higher targets
require higher caps, which mechanically raise the probability of large loss.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING

from .config import RiskConfig
from .types import Signal

if TYPE_CHECKING:
    from .state import StateStore

logger = logging.getLogger(__name__)


@dataclass
class RiskState:
    peak_equity: float
    day_start_equity: float
    current_day: date
    kill_switch_active: bool = False
    new_entries_halted: bool = False


def kelly_fraction(win_prob: float, win_loss_ratio: float) -> float:
    """Full-Kelly fraction for a bet with given win prob and payoff ratio.

    f* = p - (1 - p) / b.  Returns 0 when the edge is non-positive.
    Callers should apply a fractional-Kelly cap; full Kelly is far too volatile
    for real trading.
    """
    if win_loss_ratio <= 0:
        return 0.0
    f = win_prob - (1.0 - win_prob) / win_loss_ratio
    return max(0.0, f)


class RiskManager:
    def __init__(self, config: RiskConfig, store: "StateStore | None" = None):
        config.validate()
        self.cfg = config
        self.store = store
        self._state: RiskState | None = None

    # ------------------------------------------------------------------ state
    def initialize(self, equity: float, now: datetime | None = None) -> None:
        """Restore persisted state if available; otherwise start fresh.

        Restoring (rather than resetting peak_equity to the current value) is what
        keeps the max-drawdown kill switch honest across process restarts.
        """
        now = now or datetime.utcnow()
        restored = self.store.load_risk_state() if self.store else None
        if restored is not None:
            self._state = restored
            logger.info("Restored risk state: peak=$%.2f kill_switch=%s",
                        restored.peak_equity, restored.kill_switch_active)
        else:
            self._state = RiskState(
                peak_equity=equity,
                day_start_equity=equity,
                current_day=now.date(),
            )
        self._persist()

    @property
    def state(self) -> RiskState:
        if self._state is None:
            raise RuntimeError("RiskManager.initialize() must be called first")
        return self._state

    def _persist(self) -> None:
        if self.store is not None and self._state is not None:
            self.store.save_risk_state(self._state)

    def update_equity(self, equity: float, now: datetime | None = None) -> RiskState:
        """Feed the latest equity; update peak/daily marks and circuit breakers."""
        now = now or datetime.utcnow()
        st = self.state

        # New trading day resets the daily-loss halt (but never the kill switch).
        if now.date() != st.current_day:
            st.current_day = now.date()
            st.day_start_equity = equity
            st.new_entries_halted = False

        st.peak_equity = max(st.peak_equity, equity)

        drawdown = 0.0 if st.peak_equity <= 0 else 1.0 - equity / st.peak_equity
        if drawdown >= self.cfg.max_drawdown_limit_fraction and not st.kill_switch_active:
            st.kill_switch_active = True
            logger.error(
                "KILL SWITCH: drawdown %.2f%% >= limit %.2f%%. Flatten and stop.",
                drawdown * 100, self.cfg.max_drawdown_limit_fraction * 100,
            )

        day_loss = 0.0 if st.day_start_equity <= 0 else 1.0 - equity / st.day_start_equity
        if day_loss >= self.cfg.daily_loss_limit_fraction and not st.new_entries_halted:
            st.new_entries_halted = True
            logger.warning(
                "DAILY LOSS HALT: down %.2f%% today >= limit %.2f%%. No new entries.",
                day_loss * 100, self.cfg.daily_loss_limit_fraction * 100,
            )
        self._persist()
        return st

    def can_open_new_risk(self) -> bool:
        st = self.state
        return not st.kill_switch_active and not st.new_entries_halted

    def reset_kill_switch(self) -> None:
        """Manual, deliberate override after a kill-switch trip."""
        self.state.kill_switch_active = False
        self._persist()
        logger.warning("Kill switch manually reset.")

    # ----------------------------------------------------------------- sizing
    def target_shares(
        self,
        equity: float,
        price: float,
        signal: Signal,
        recent_annual_vol: float | None = None,
    ) -> float:
        """Translate a [-1, 1] signal into a signed whole-share target.

        Order of operations:
          1. Base notional = target * max_position_fraction * equity.
          2. Volatility targeting scales toward target_annual_vol (down-only
             relative to the cap, since the cap is reapplied afterwards).
          3. Per-trade stop risk caps shares so a stop-out loses no more than
             risk_per_trade_fraction of equity.
          4. The max_position_fraction notional cap is hard-enforced last.
        """
        if price <= 0 or equity <= 0 or signal.target == 0.0:
            return 0.0

        cap_notional = self.cfg.max_position_fraction * equity
        notional = signal.target * cap_notional

        # 2) Volatility targeting.
        if (self.cfg.target_annual_vol is not None
                and recent_annual_vol is not None and recent_annual_vol > 0):
            scale = self.cfg.target_annual_vol / recent_annual_vol
            notional *= scale

        # 4a) Hard cap notional magnitude.
        if abs(notional) > cap_notional:
            notional = cap_notional * (1.0 if notional > 0 else -1.0)

        shares = notional / price

        # 3) Per-trade stop-loss risk cap.
        if signal.stop_price is not None and self.cfg.risk_per_trade_fraction > 0:
            stop_distance = abs(price - signal.stop_price)
            if stop_distance > 0:
                max_risk_shares = (self.cfg.risk_per_trade_fraction * equity) / stop_distance
                if abs(shares) > max_risk_shares:
                    shares = max_risk_shares * (1.0 if shares > 0 else -1.0)

        return float(int(shares))  # truncate toward zero -> whole shares

    def clamp_to_leverage(
        self, proposed_notional: float, current_gross_notional: float, equity: float
    ) -> float:
        """Reduce a proposed position notional so total gross leverage stays
        within max_gross_leverage. Returns the allowed notional magnitude."""
        if equity <= 0:
            return 0.0
        max_gross = self.cfg.max_gross_leverage * equity
        headroom = max(0.0, max_gross - current_gross_notional)
        return min(abs(proposed_notional), headroom)
