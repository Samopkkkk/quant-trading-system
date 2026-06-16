"""TradingAgent: the live/paper orchestrator.

Each cycle it: reads account equity, updates the risk circuit breakers, and for
every symbol pulls recent CLOSED bars, asks the strategy for intent, sizes it
through the RiskManager, and rebalances via the broker.

Safety posture:
  * Paper broker by default; live requires explicit config + env credentials.
  * The max-drawdown kill switch flattens everything and stops trading.
  * A daily-loss halt blocks new exposure but still lets positions be reduced.
"""
from __future__ import annotations

from datetime import datetime
import logging
import time
from typing import Callable

import numpy as np
import pandas as pd

from . import data as market_data
from .broker import Broker
from .config import AgentConfig
from .marketclock import ET, is_market_open, next_close_reason
from .risk import RiskManager
from .screener import select_symbols
from .state import StateStore
from .strategies import Strategy
from .types import Fill, Order, OrderStatus, OrderType, Side

logger = logging.getLogger(__name__)

HistoryProvider = Callable[[str], pd.DataFrame]

_TERMINAL_STATUSES = {"FILLED", "CANCELLED", "CANCELED", "REJECTED", "FAILED", "EXPIRED"}


def _order_is_terminal(payload: object) -> bool:
    """Best-effort: does a broker order-status payload indicate a final state?"""
    if isinstance(payload, dict):
        for key in ("status", "order_status", "orderStatus"):
            val = payload.get(key)
            if isinstance(val, str):
                return val.upper().replace(" ", "_") in _TERMINAL_STATUSES
        if isinstance(payload.get("data"), dict):
            return _order_is_terminal(payload["data"])
    return False  # unknown shape -> treat as still pending (a TTL prevents deadlock)


class TradingAgent:
    def __init__(
        self,
        config: AgentConfig,
        strategy: Strategy,
        broker: Broker,
        risk: RiskManager | None = None,
        history_provider: HistoryProvider | None = None,
        clock: Callable[[], datetime] | None = None,
        vol_window: int = 20,
        periods_per_year: int = 252,
    ):
        config.validate()
        self.cfg = config
        self.strategy = strategy
        self.broker = broker
        self.store = StateStore(config.state_path) if config.state_path else None
        self.risk = risk or RiskManager(config.risk, store=self.store)
        self.history_provider = history_provider or (
            lambda s: market_data.get_history(s, range_="1y", interval="1d")
        )
        self.clock = clock or (lambda: datetime.now(ET))
        self.vol_window = vol_window
        self.periods_per_year = periods_per_year
        self._initialized = False
        # Symbols with an order submitted but not yet confirmed filled. Prevents
        # stacking a duplicate order while the first is still working.
        self._inflight: dict[str, str] = {}
        self._inflight_age: dict[str, int] = {}
        self.max_inflight_cycles = 6
        # The symbols currently traded. With a universe configured this is the
        # screened selection; otherwise it is the fixed config list.
        self.active_symbols: list[str] = list(config.symbols)
        self._cycle = 0

    # ------------------------------------------------------------------ cycle
    def _ensure_initialized(self) -> None:
        if not self._initialized:
            self.risk.initialize(self.broker.get_account().equity)
            self._initialized = True

    def run_once(self) -> None:
        if self.cfg.enforce_market_hours and not is_market_open(self.clock()):
            logger.info("Market closed (%s); skipping cycle.", next_close_reason(self.clock()))
            return
        self._ensure_initialized()
        self._maybe_rescreen()
        self._reconcile_inflight()
        account = self.broker.get_account()
        state = self.risk.update_equity(account.equity)
        logger.info("Equity=$%.2f | symbols=%s | kill_switch=%s | new_entries_halted=%s",
                    account.equity, self.active_symbols, state.kill_switch_active,
                    state.new_entries_halted)

        if state.kill_switch_active:
            logger.error("Kill switch active — flattening all positions.")
            self.flatten_all()
            self._cycle += 1
            return

        for symbol in self.active_symbols:
            try:
                self._handle_symbol(symbol, account.equity)
            except Exception:
                logger.exception("Error handling %s", symbol)
        self._cycle += 1

    def _maybe_rescreen(self) -> None:
        """Re-select the trading universe from the candidate pool (新标的选择)."""
        if not self.cfg.universe:
            return
        if self._cycle % self.cfg.rescreen_every != 0:
            return
        histories: dict = {}
        for sym in self.cfg.universe:
            try:
                histories[sym] = self.history_provider(sym)
            except Exception:
                logger.exception("Could not fetch history for %s during screen", sym)
        selected = select_symbols(histories, top_n=self.cfg.screen_top_n)
        if not selected or selected == self.active_symbols:
            return
        dropped = [s for s in self.active_symbols if s not in selected]
        for sym in dropped:                       # exit names that fell out of the book
            self._flatten_symbol(sym)
        logger.info("Universe re-screened: %s -> %s", self.active_symbols, selected)
        self.active_symbols = selected

    def _handle_symbol(self, symbol: str, equity: float) -> None:
        history = self.history_provider(symbol)
        if history is None or len(history) < 2:
            logger.warning("No usable history for %s; skipping.", symbol)
            return

        price = float(history["close"].iloc[-1])
        if hasattr(self.broker, "update_price"):
            self.broker.update_price(symbol, price)        # paper broker needs a mark

        signal = self.strategy.evaluate(symbol, history)
        recent_vol = self._recent_vol(history)
        target = self.risk.target_shares(equity, price, signal, recent_vol)

        cur = self.broker.get_positions().get(symbol)
        cur_qty = cur.quantity if cur else 0.0
        if not self.risk.can_open_new_risk() and abs(target) > abs(cur_qty):
            target = cur_qty                                # halt: no new exposure

        delta = target - cur_qty
        if abs(delta) < 1:
            return
        if symbol in self._inflight:
            logger.info("%s has an in-flight order (%s); skipping new order this cycle.",
                        symbol, self._inflight[symbol])
            return
        side = Side.BUY if delta > 0 else Side.SELL
        fill = self.broker.submit_order(
            Order(symbol=symbol, side=side, quantity=abs(delta), order_type=OrderType.MARKET)
        )
        logger.info("%s %s %.0f @ ~%.2f (%s) status=%s",
                    side.value, symbol, abs(delta), price, signal.reason, fill.status.value)
        self._track_inflight(symbol, fill)
        self._log_fill(fill)

    def _track_inflight(self, symbol: str, fill: Fill) -> None:
        if fill.status in (OrderStatus.PENDING, OrderStatus.PARTIAL) and fill.broker_order_id:
            self._inflight[symbol] = fill.broker_order_id
            self._inflight_age[symbol] = 0
        else:                                   # FILLED / REJECTED / CANCELLED -> not working
            self._inflight.pop(symbol, None)
            self._inflight_age.pop(symbol, None)

    def _reconcile_inflight(self) -> None:
        """Clear symbols whose working order has reached a terminal state."""
        if not hasattr(self.broker, "get_order_status"):
            self._inflight.clear()              # broker fills synchronously (e.g. paper)
            self._inflight_age.clear()
            return
        for symbol, coid in list(self._inflight.items()):
            terminal = False
            try:
                terminal = _order_is_terminal(self.broker.get_order_status(coid))
            except Exception:
                logger.exception("Reconcile failed for %s (%s)", symbol, coid)
            self._inflight_age[symbol] = self._inflight_age.get(symbol, 0) + 1
            if terminal or self._inflight_age[symbol] > self.max_inflight_cycles:
                if not terminal:
                    logger.warning("Order %s for %s unresolved after %d cycles; clearing.",
                                   coid, symbol, self.max_inflight_cycles)
                self._inflight.pop(symbol, None)
                self._inflight_age.pop(symbol, None)

    def _log_fill(self, fill: Fill) -> None:
        if self.store is None:
            return
        self.store.append_trade({
            "timestamp": fill.timestamp.isoformat(),
            "symbol": fill.order.symbol,
            "side": fill.order.side.value,
            "quantity": fill.filled_quantity,
            "price": fill.fill_price,
            "status": fill.status.value,
            "broker_order_id": fill.broker_order_id,
        })

    def _flatten_symbol(self, symbol: str) -> None:
        pos = self.broker.get_positions().get(symbol)
        if pos is None or pos.quantity == 0:
            return
        side = Side.SELL if pos.quantity > 0 else Side.BUY
        if hasattr(self.broker, "update_price") and pos.last_price:
            self.broker.update_price(symbol, pos.last_price)
        fill = self.broker.submit_order(
            Order(symbol=symbol, side=side, quantity=abs(pos.quantity),
                  order_type=OrderType.MARKET)
        )
        logger.info("Flatten %s %.0f", symbol, abs(pos.quantity))
        self._log_fill(fill)

    def flatten_all(self) -> None:
        for symbol in list(self.broker.get_positions()):
            self._flatten_symbol(symbol)

    def run(self, max_cycles: int | None = None,
            sleep_fn: Callable[[float], None] = time.sleep) -> None:
        logger.info("Agent starting | symbols=%s | live=%s",
                    self.cfg.symbols, self.cfg.live)
        cycle = 0
        while max_cycles is None or cycle < max_cycles:
            self.run_once()
            cycle += 1
            if max_cycles is not None and cycle >= max_cycles:
                break
            sleep_fn(self.cfg.poll_interval_seconds)

    def _recent_vol(self, history: pd.DataFrame) -> float | None:
        if len(history) < self.vol_window + 1:
            return None
        rets = history["close"].pct_change().dropna().tail(self.vol_window)
        if len(rets) < 2 or rets.std() == 0:
            return None
        return float(rets.std() * np.sqrt(self.periods_per_year))
