"""Broker abstraction.

`PaperBroker` simulates fills locally (commission + slippage) and works fully
offline, so backtests and dry runs need no credentials.

`WebullBroker` is a thin adapter over the official Webull OpenAPI SDK
(`webull-python-sdk-core` + `webull-python-sdk-trade`). It targets the real SDK
call surface (ApiClient / Account / OrderOperation). It is lazily imported so
the rest of the system runs without the SDK installed, and it raises clear
errors rather than silently pretending an order succeeded.
"""
from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime

from .config import AgentConfig
from .types import (
    AccountSnapshot, Fill, Order, OrderStatus, OrderType, Position, Side,
)

logger = logging.getLogger(__name__)


class Broker(ABC):
    @abstractmethod
    def get_account(self) -> AccountSnapshot: ...

    @abstractmethod
    def get_positions(self) -> dict[str, Position]: ...

    @abstractmethod
    def submit_order(self, order: Order) -> Fill: ...

    @abstractmethod
    def cancel_order(self, broker_order_id: str) -> bool: ...


# --------------------------------------------------------------------------- #
#  Paper broker
# --------------------------------------------------------------------------- #
class PaperBroker(Broker):
    """Local simulated broker. Fills market orders at last price +/- slippage."""

    def __init__(self, config: AgentConfig):
        self.cfg = config
        self.cash = config.initial_capital
        self.positions: dict[str, Position] = {}
        self.last_prices: dict[str, float] = {}
        self.fills: list[Fill] = []

    def update_price(self, symbol: str, price: float) -> None:
        self.last_prices[symbol] = price
        if symbol in self.positions:
            self.positions[symbol].last_price = price

    def _commission(self, qty: float) -> float:
        return max(self.cfg.commission_min, self.cfg.commission_per_share * abs(qty))

    def get_account(self) -> AccountSnapshot:
        mv = sum(p.quantity * self.last_prices.get(s, p.avg_price)
                 for s, p in self.positions.items())
        equity = self.cash + mv
        return AccountSnapshot(
            cash=self.cash, equity=equity, buying_power=max(0.0, self.cash),
            positions=dict(self.positions), timestamp=datetime.utcnow(),
        )

    def get_positions(self) -> dict[str, Position]:
        return dict(self.positions)

    def submit_order(self, order: Order) -> Fill:
        ref = order.limit_price or self.last_prices.get(order.symbol)
        if ref is None:
            raise RuntimeError(
                f"PaperBroker has no price for {order.symbol}; call update_price first"
            )
        signed_qty = order.quantity if order.side == Side.BUY else -order.quantity

        # Limit orders only fill if marketable against the last price.
        if order.order_type == OrderType.LIMIT and order.limit_price is not None:
            last = self.last_prices.get(order.symbol, order.limit_price)
            if (order.side == Side.BUY and order.limit_price < last) or \
               (order.side == Side.SELL and order.limit_price > last):
                return Fill(order, ref, 0.0, 0.0, datetime.utcnow(),
                            status=OrderStatus.PENDING)

        slip = self.cfg.slippage_bps / 10_000.0
        fill_price = ref * (1 + slip) if order.side == Side.BUY else ref * (1 - slip)
        commission = self._commission(order.quantity)

        self.cash -= signed_qty * fill_price + commission
        self._apply_fill(order.symbol, signed_qty, fill_price)
        self.update_price(order.symbol, fill_price)

        fill = Fill(order, fill_price, order.quantity, commission, datetime.utcnow(),
                    status=OrderStatus.FILLED, broker_order_id=str(uuid.uuid4()))
        self.fills.append(fill)
        return fill

    def _apply_fill(self, symbol: str, signed_qty: float, price: float) -> None:
        pos = self.positions.get(symbol)
        cur = pos.quantity if pos else 0.0
        new = cur + signed_qty
        if pos is None or cur == 0:
            avg = price
        elif (cur > 0) == (signed_qty > 0):           # adding to position
            avg = (pos.avg_price * cur + price * signed_qty) / new
        elif abs(signed_qty) <= abs(cur):             # reducing, avg unchanged
            avg = pos.avg_price
        else:                                          # flipping through zero
            avg = price
        if abs(new) < 1e-9:
            self.positions.pop(symbol, None)
        else:
            self.positions[symbol] = Position(symbol, new, avg, price)

    def cancel_order(self, broker_order_id: str) -> bool:
        return True  # paper fills are immediate; nothing to cancel


# --------------------------------------------------------------------------- #
#  Webull broker (real)
# --------------------------------------------------------------------------- #
class WebullBroker(Broker):
    """Adapter over the official Webull OpenAPI SDK.

    Requires `pip install webull-python-sdk-core webull-python-sdk-trade` and
    valid credentials. Symbol -> instrument_id resolution uses an explicit map
    (recommended, set via WEBULL_INSTRUMENT_IDS) or a best-effort SDK lookup.
    """

    def __init__(self, config: AgentConfig, instrument_id_map: dict[str, str] | None = None):
        config.require_live_credentials()
        self.cfg = config
        self.account_id = config.webull_account_id
        self._instrument_ids = dict(instrument_id_map or {})
        self._import_sdk()
        self._build_clients()

    def _import_sdk(self) -> None:
        try:
            from webullsdkcore.client import ApiClient
            from webullsdktrade.trade.account_info import Account
            from webullsdktrade.trade.order_operation import OrderOperation
            from webullsdktrade.trade.trade_instrument import TradeInstrument
        except ImportError as exc:
            raise RuntimeError(
                "Webull SDK not installed. Run: "
                "pip install webull-python-sdk-core webull-python-sdk-trade"
            ) from exc
        self._ApiClient = ApiClient
        self._Account = Account
        self._OrderOperation = OrderOperation
        self._TradeInstrument = TradeInstrument

    def _build_clients(self) -> None:
        client = self._ApiClient(
            self.cfg.webull_app_key, self.cfg.webull_app_secret, self.cfg.webull_region,
        )
        client.add_endpoint(self.cfg.webull_region, self.cfg.webull_endpoint)
        self.client = client
        self.account = self._Account(client)
        self.orders = self._OrderOperation(client)
        self.instruments = self._TradeInstrument(client)
        logger.info(
            "WebullBroker connected (endpoint=%s, account=%s***)",
            self.cfg.webull_endpoint, self.account_id[:6],
        )

    # ---- helpers ----
    @staticmethod
    def _json(response):
        if response is None or getattr(response, "status_code", 200) >= 400:
            raise RuntimeError(f"Webull API error: "
                               f"{getattr(response, 'status_code', '?')} "
                               f"{getattr(response, 'text', '')[:200]}")
        return response.json()

    def _resolve_instrument_id(self, symbol: str) -> str:
        if symbol in self._instrument_ids:
            return self._instrument_ids[symbol]
        # Best-effort lookup; the explicit map is the reliable path.
        try:
            resp = self.instruments.get_trade_security_detail(
                symbol=symbol, market="US", instrument_super_type="SECURITY",
                instrument_type="STOCK", strike_price=None, init_exp_date=None,
            )
            data = self._json(resp)
            items = data.get("data") if isinstance(data, dict) else data
            inst_id = (items[0] if isinstance(items, list) and items else {}).get("instrument_id")
            if inst_id:
                self._instrument_ids[symbol] = str(inst_id)
                return str(inst_id)
        except Exception as exc:
            logger.warning("Instrument lookup failed for %s: %s", symbol, exc)
        raise RuntimeError(
            f"Cannot resolve instrument_id for {symbol}. Provide it via "
            f"WEBULL_INSTRUMENT_IDS='{symbol}:<id>'."
        )

    def get_account(self) -> AccountSnapshot:
        data = self._json(self.account.get_account_balance(self.account_id, "USD"))
        cash = float(data.get("cash_balance", data.get("cashBalance", 0)) or 0)
        equity = float(data.get("net_liquidation_value",
                                data.get("totalEquity", cash)) or cash)
        bp = float(data.get("buying_power", data.get("buyPower", 0)) or 0)
        return AccountSnapshot(cash=cash, equity=equity, buying_power=bp,
                               positions=self.get_positions(), timestamp=datetime.utcnow())

    def get_positions(self) -> dict[str, Position]:
        data = self._json(self.account.get_account_position(self.account_id))
        rows = data.get("data", data) if isinstance(data, dict) else data
        positions: dict[str, Position] = {}
        for r in rows or []:
            sym = r.get("symbol") or r.get("ticker")
            qty = float(r.get("quantity", r.get("position", 0)) or 0)
            if not sym or qty == 0:
                continue
            positions[sym] = Position(
                symbol=sym, quantity=qty,
                avg_price=float(r.get("cost_price", r.get("costPrice", 0)) or 0),
                last_price=float(r.get("last_price", r.get("lastPrice", 0)) or 0),
            )
        return positions

    def submit_order(self, order: Order) -> Fill:
        side = "BUY" if order.side == Side.BUY else "SELL"
        otype = "MARKET" if order.order_type == OrderType.MARKET else "LIMIT"
        coid = order.client_order_id or uuid.uuid4().hex[:32]
        instrument_id = self._resolve_instrument_id(order.symbol)
        resp = self.orders.place_order(
            account_id=self.account_id, qty=int(order.quantity),
            instrument_id=instrument_id, side=side, client_order_id=coid,
            order_type=otype, extended_hours_trading=False, tif=order.tif.value,
            limit_price=order.limit_price,
        )
        data = self._json(resp)
        return Fill(order=order, fill_price=order.limit_price or 0.0,
                    filled_quantity=order.quantity, commission=0.0,
                    timestamp=datetime.utcnow(), status=OrderStatus.PENDING,
                    broker_order_id=str(data.get("client_order_id", coid)))

    def cancel_order(self, broker_order_id: str) -> bool:
        resp = self.orders.cancel_order(self.account_id, broker_order_id)
        self._json(resp)
        return True


def make_broker(config: AgentConfig) -> Broker:
    """Factory: PaperBroker unless config.live is explicitly True."""
    if config.live:
        logger.warning("LIVE trading enabled — real orders will be sent to Webull.")
        return WebullBroker(config)
    return PaperBroker(config)
