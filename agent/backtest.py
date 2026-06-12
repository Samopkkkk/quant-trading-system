"""Event-driven backtester with NO look-ahead bias.

Convention that prevents cheating:
  * At bar t, the strategy only sees bars [0 .. t-1] (CLOSED bars).
  * The resulting order fills at bar t's OPEN (with slippage + commission).
  * Equity is marked at bar t's CLOSE.

So a decision can never use information from the bar it trades on. Fills go
through the same PaperBroker used for live paper trading, so the execution
model is identical in backtest and forward test.

Metrics are computed honestly from the realized equity curve and round-trip
trades. They describe ONE historical path; they are not a prediction, still
less a guarantee.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .broker import PaperBroker
from .config import AgentConfig
from .risk import RiskManager
from .strategies import Strategy
from .types import Fill, Order, OrderType, Side


@dataclass
class Metrics:
    total_return: float = 0.0
    cagr: float = 0.0
    annual_vol: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    max_drawdown: float = 0.0
    calmar: float = 0.0
    num_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    final_equity: float = 0.0


@dataclass
class BacktestReport:
    equity_curve: pd.Series
    fills: list[Fill] = field(default_factory=list)
    realized_pnls: list[float] = field(default_factory=list)
    metrics: Metrics = field(default_factory=Metrics)

    def summary(self) -> str:
        m = self.metrics
        return (
            "==================== Backtest Report ====================\n"
            f"  Final equity     : ${m.final_equity:,.2f}\n"
            f"  Total return     : {m.total_return * 100:,.2f}%\n"
            f"  CAGR             : {m.cagr * 100:,.2f}%\n"
            f"  Annual volatility: {m.annual_vol * 100:,.2f}%\n"
            f"  Sharpe ratio     : {m.sharpe:,.2f}\n"
            f"  Sortino ratio    : {m.sortino:,.2f}\n"
            f"  Max drawdown     : {m.max_drawdown * 100:,.2f}%\n"
            f"  Calmar ratio     : {m.calmar:,.2f}\n"
            f"  Round-trip trades: {m.num_trades}\n"
            f"  Win rate         : {m.win_rate * 100:,.2f}%\n"
            f"  Profit factor    : {m.profit_factor:,.2f}\n"
            "========================================================="
        )


def realized_pnls_from_fills(fills: list[Fill]) -> list[float]:
    """Reconstruct round-trip P&L using average-cost accounting."""
    pos_qty = 0.0
    avg = 0.0
    realized: list[float] = []
    for f in fills:
        if f.filled_quantity == 0:
            continue
        signed = f.filled_quantity if f.order.side == Side.BUY else -f.filled_quantity
        price = f.fill_price
        if pos_qty == 0 or (pos_qty > 0) == (signed > 0):      # open / add
            new = pos_qty + signed
            avg = (avg * pos_qty + price * signed) / new if new != 0 else 0.0
            pos_qty = new
        else:                                                   # reduce / close / flip
            closing = min(abs(signed), abs(pos_qty))
            direction = 1.0 if pos_qty > 0 else -1.0
            realized.append((price - avg) * closing * direction - f.commission)
            pos_qty += signed
            if abs(signed) > closing:                           # flipped through zero
                avg = price
    return realized


def compute_metrics(equity: pd.Series, realized: list[float],
                    periods_per_year: int = 252) -> Metrics:
    m = Metrics()
    if len(equity) < 2:
        m.final_equity = float(equity.iloc[-1]) if len(equity) else 0.0
        return m

    start, end = float(equity.iloc[0]), float(equity.iloc[-1])
    m.final_equity = end
    m.total_return = end / start - 1.0

    rets = equity.pct_change().dropna()
    n = len(rets)
    if start > 0 and end > 0 and n > 0:
        m.cagr = (end / start) ** (periods_per_year / n) - 1.0
    if n > 1 and rets.std() > 0:
        m.annual_vol = float(rets.std() * np.sqrt(periods_per_year))
        m.sharpe = float(rets.mean() / rets.std() * np.sqrt(periods_per_year))
        downside = rets[rets < 0]
        if len(downside) > 0 and downside.std() > 0:
            m.sortino = float(rets.mean() / downside.std() * np.sqrt(periods_per_year))

    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    m.max_drawdown = float(-drawdown.min())
    if m.max_drawdown > 0:
        m.calmar = m.cagr / m.max_drawdown

    m.num_trades = len(realized)
    if realized:
        wins = [p for p in realized if p > 0]
        losses = [p for p in realized if p < 0]
        m.win_rate = len(wins) / len(realized)
        gross_win = sum(wins)
        gross_loss = abs(sum(losses))
        m.profit_factor = (gross_win / gross_loss) if gross_loss > 0 else float("inf")
    return m


class Backtester:
    """Single-symbol event-driven backtest (multi-symbol portfolio is a TODO)."""

    def __init__(self, config: AgentConfig, strategy: Strategy,
                 vol_window: int = 20, periods_per_year: int = 252):
        self.cfg = config
        self.strategy = strategy
        self.vol_window = vol_window
        self.periods_per_year = periods_per_year

    def run(self, symbol: str, prices: pd.DataFrame) -> BacktestReport:
        required = {"open", "high", "low", "close"}
        if not required.issubset(prices.columns):
            raise ValueError(f"prices must contain columns {required}")
        prices = prices.sort_index()

        broker = PaperBroker(self.cfg)
        risk = RiskManager(self.cfg.risk)
        risk.initialize(self.cfg.initial_capital,
                        now=prices.index[0].to_pydatetime())

        equity_points: list[float] = []
        index: list = []

        for t in range(len(prices)):
            bar = prices.iloc[t]
            ts = prices.index[t].to_pydatetime()
            open_px, close_px = float(bar["open"]), float(bar["close"])

            if t >= 1:
                history = prices.iloc[:t]                      # CLOSED bars only
                broker.update_price(symbol, open_px)           # trade at the open
                equity_now = broker.get_account().equity

                signal = self.strategy.evaluate(symbol, history)
                recent_vol = self._recent_vol(history)
                target = risk.target_shares(equity_now, open_px, signal, recent_vol)

                # Circuit breakers: kill switch flattens; daily halt blocks
                # *increasing* exposure but still allows reducing it.
                cur = broker.get_positions().get(symbol)
                cur_qty = cur.quantity if cur else 0.0
                if risk.state.kill_switch_active:
                    target = 0.0
                elif not risk.can_open_new_risk() and abs(target) > abs(cur_qty):
                    target = cur_qty

                self._rebalance(broker, symbol, cur_qty, target, open_px)

            broker.update_price(symbol, close_px)              # mark at the close
            equity = broker.get_account().equity
            risk.update_equity(equity, ts)
            equity_points.append(equity)
            index.append(prices.index[t])

        curve = pd.Series(equity_points, index=pd.DatetimeIndex(index, name="date"))
        realized = realized_pnls_from_fills(broker.fills)
        metrics = compute_metrics(curve, realized, self.periods_per_year)
        return BacktestReport(curve, broker.fills, realized, metrics)

    def _recent_vol(self, history: pd.DataFrame) -> float | None:
        if len(history) < self.vol_window + 1:
            return None
        rets = history["close"].pct_change().dropna().tail(self.vol_window)
        if len(rets) < 2 or rets.std() == 0:
            return None
        return float(rets.std() * np.sqrt(self.periods_per_year))

    @staticmethod
    def _rebalance(broker: PaperBroker, symbol: str, cur_qty: float,
                   target_qty: float, price: float) -> None:
        delta = target_qty - cur_qty
        if abs(delta) < 1:
            return
        side = Side.BUY if delta > 0 else Side.SELL
        broker.submit_order(Order(symbol=symbol, side=side, quantity=abs(delta),
                                  order_type=OrderType.MARKET))
