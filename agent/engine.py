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
from .state import StateStore
from .strategies import Strategy
from .types import Fill, Order, OrderType, Side

logger = logging.getLogger(__name__)

HistoryProvider = Callable[[str], pd.DataFrame]


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
        account = self.broker.get_account()
        state = self.risk.update_equity(account.equity)
        logger.info("Equity=$%.2f | kill_switch=%s | new_entries_halted=%s",
                    account.equity, state.kill_switch_active, state.new_entries_halted)

        if state.kill_switch_active:
            logger.error("Kill switch active — flattening all positions.")
            self.flatten_all()
            return

        for symbol in self.cfg.symbols:
            try:
                self._handle_symbol(symbol, account.equity)
            except Exception:
                logger.exception("Error handling %s", symbol)

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
        side = Side.BUY if delta > 0 else Side.SELL
        fill = self.broker.submit_order(
            Order(symbol=symbol, side=side, quantity=abs(delta), order_type=OrderType.MARKET)
        )
        logger.info("%s %s %.0f @ ~%.2f (%s) status=%s",
                    side.value, symbol, abs(delta), price, signal.reason, fill.status.value)
        self._log_fill(fill)

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

    def flatten_all(self) -> None:
        for symbol, pos in self.broker.get_positions().items():
            if pos.quantity == 0:
                continue
            side = Side.SELL if pos.quantity > 0 else Side.BUY
            if hasattr(self.broker, "update_price") and pos.last_price:
                self.broker.update_price(symbol, pos.last_price)
            fill = self.broker.submit_order(
                Order(symbol=symbol, side=side, quantity=abs(pos.quantity),
                      order_type=OrderType.MARKET)
            )
            logger.info("Flatten %s %.0f", symbol, abs(pos.quantity))
            self._log_fill(fill)

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
