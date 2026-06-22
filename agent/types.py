"""Core data types shared across the trading agent.

These are deliberately small, immutable-ish dataclasses so that every layer
(strategy, risk, broker, backtest) speaks the same vocabulary.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class TimeInForce(str, Enum):
    DAY = "DAY"
    GTC = "GTC"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class Bar:
    """A single OHLCV candle."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class Quote:
    symbol: str
    price: float
    timestamp: datetime
    bid: Optional[float] = None
    ask: Optional[float] = None


@dataclass
class Order:
    symbol: str
    side: Side
    quantity: float
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    tif: TimeInForce = TimeInForce.DAY
    client_order_id: Optional[str] = None


@dataclass
class Fill:
    order: Order
    fill_price: float
    filled_quantity: float
    commission: float
    timestamp: datetime
    status: OrderStatus = OrderStatus.FILLED
    broker_order_id: Optional[str] = None


@dataclass
class Position:
    symbol: str
    quantity: float           # signed: positive = long, negative = short
    avg_price: float
    last_price: float = 0.0

    @property
    def market_value(self) -> float:
        return self.quantity * self.last_price

    @property
    def unrealized_pnl(self) -> float:
        return (self.last_price - self.avg_price) * self.quantity


@dataclass
class AccountSnapshot:
    cash: float
    equity: float                       # cash + market value of positions
    buying_power: float = 0.0
    positions: dict[str, Position] = field(default_factory=dict)
    timestamp: Optional[datetime] = None


@dataclass
class Signal:
    """A strategy's desired exposure for the *next* bar.

    `target` is a dimensionless weight in [-1, 1]:
        +1.0 = take the largest long the risk budget allows
         0.0 = flat
        -1.0 = largest short the risk budget allows

    The strategy expresses *intent*; the RiskManager decides the actual
    share quantity. This keeps alpha and sizing cleanly separated.
    """
    symbol: str
    target: float
    stop_price: Optional[float] = None
    reason: str = ""

    def __post_init__(self) -> None:
        # Clamp defensively so a buggy strategy can never request >100% intent.
        self.target = max(-1.0, min(1.0, float(self.target)))
