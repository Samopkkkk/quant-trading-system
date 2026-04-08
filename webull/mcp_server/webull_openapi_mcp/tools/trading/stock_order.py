"""Stock order tools for Webull MCP Server.

Provides stock order tools via register_stock_order_tools:
- place_stock_order: Single stock order (non-combo)
- preview_stock_order: Preview order without submitting
- replace_stock_order: Modify existing stock order

Provides combo order tools via register_combo_order_tools:
- place_stock_combo_order: Combo orders (OTO, OCO, OTOCO)

Provides algo order tools via register_algo_order_tools:
- place_algo_order: Algorithmic orders (TWAP, VWAP, POV)

Note: Uses order_v3 SDK API (OrderOperationV3).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, Optional

from webull_openapi_mcp.errors import ValidationError, handle_sdk_exception
from webull_openapi_mcp.formatters import prepend_disclaimer, extract_response_data, format_order_preview
from webull_openapi_mcp.guards import validate_stock_order, validate_client_order_id, validate_combo_order, validate_algo_order

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from webull_openapi_mcp.audit import AuditLogger
    from webull_openapi_mcp.config import ServerConfig
    from webull_openapi_mcp.sdk_client import WebullSDKClient


def _generate_client_order_id() -> str:
    """Generate a unique client order ID if not provided."""
    return str(uuid.uuid4()).replace("-", "")[:32]


def _format_order_result(data: dict) -> str:
    """Format order result to standard format."""
    result = {}
    if "client_order_id" in data:
        result["client_order_id"] = data["client_order_id"]
    if "client_combo_order_id" in data:
        result["client_combo_order_id"] = data["client_combo_order_id"]
    if "combo_order_id" in data:
        result["combo_order_id"] = data["combo_order_id"]
    if "order_id" in data:
        result["order_id"] = data["order_id"]

    if not result:
        return str(data)

    lines = [f"{k}: {v}" for k, v in result.items()]
    return "\n".join(lines)


def _add_optional_str(order: dict, key: str, value: Any) -> None:
    """Add a value to order dict as string if not None."""
    if value is not None:
        order[key] = str(value)


def _build_stock_order(params: dict) -> dict:
    """Build a single stock order dict for the SDK.

    Required keys: coid, market, symbol, side, order_type, time_in_force,
    entrust_type, trading_session, quantity.
    Optional keys: total_cash_amount, limit_price, stop_price,
    extended_hours, trailing_type, trailing_stop_step.
    """
    entrust_type = params["entrust_type"]
    order: dict = {
        "combo_type": "NORMAL",
        "client_order_id": params["coid"],
        "instrument_type": "EQUITY",
        "market": params["market"],
        "symbol": params["symbol"],
        "order_type": params["order_type"],
        "entrust_type": entrust_type,
        "support_trading_session": params["trading_session"],
        "time_in_force": params["time_in_force"],
        "side": params["side"],
    }

    if entrust_type == "AMOUNT" and params.get("total_cash_amount") is not None:
        order["total_cash_amount"] = str(params["total_cash_amount"])
    else:
        order["quantity"] = str(params["quantity"])

    _add_optional_str(order, "limit_price", params.get("limit_price"))
    _add_optional_str(order, "stop_price", params.get("stop_price"))
    if params.get("extended_hours"):
        order["extended_hours"] = params["extended_hours"]
    _add_optional_str(order, "trailing_type", params.get("trailing_type"))
    _add_optional_str(order, "trailing_stop_step", params.get("trailing_stop_step"))
    _add_optional_str(order, "expire_date", params.get("expire_date"))

    return order


# Fields that can be modified on a stock/algo order, with their conversion rules.
# key -> (output_key, convert_to_str)
_MODIFY_FIELDS: dict[str, tuple[str, bool]] = {
    "quantity": ("quantity", True),
    "limit_price": ("limit_price", True),
    "stop_price": ("stop_price", True),
    "time_in_force": ("time_in_force", False),
    "expire_date": ("expire_date", False),
    "order_type": ("order_type", False),
    "trailing_type": ("trailing_type", False),
    "trailing_stop_step": ("trailing_stop_step", True),
    "target_vol_percent": ("target_vol_percent", True),
    "max_target_percent": ("max_target_percent", True),
    "algo_start_time": ("algo_start_time", False),
    "algo_end_time": ("algo_end_time", False),
}


def _build_modify_order(order_args: dict) -> dict:
    """Build a modify-order dict from the provided arguments."""
    modify_order: dict = {"client_order_id": order_args["client_order_id"]}
    for key, (out_key, to_str) in _MODIFY_FIELDS.items():
        if key in order_args:
            modify_order[out_key] = str(order_args[key]) if to_str else order_args[key]
    return modify_order


def _collect_replace_args(**kwargs: Any) -> dict:
    """Collect non-None keyword arguments into a dict."""
    return {k: v for k, v in kwargs.items() if v is not None}


def _build_combo_leg(order: dict) -> dict:
    """Build a single combo order leg dict."""
    leg: dict = {
        "combo_type": order.get("combo_type", "NORMAL"),
        "instrument_type": order.get("instrument_type", "EQUITY"),
        "market": order.get("market", "US"),
        "symbol": order["symbol"],
        "side": order["side"],
        "order_type": order["order_type"],
        "quantity": str(order["quantity"]),
        "entrust_type": "QTY",
        "time_in_force": order.get("time_in_force", "DAY"),
        "support_trading_session": order.get("support_trading_session", "CORE"),
    }
    if order.get("option_strategy") or order.get("instrument_type") == "OPTION":
        leg["option_strategy"] = order.get("option_strategy", "SINGLE")
    leg["client_order_id"] = order.get("client_order_id") or _generate_client_order_id()
    _add_optional_str(leg, "limit_price", order.get("limit_price"))
    _add_optional_str(leg, "stop_price", order.get("stop_price"))
    return leg


def _build_algo_order(
    coid: str,
    symbol: str,
    side: str,
    quantity: float,
    algo_type: str,
    effective_order_type: str,
    limit_price: float | None,
    algo_start_time: str | None,
    algo_end_time: str | None,
    target_vol_percent: int | None,
    max_target_percent: int | None,
) -> dict:
    """Build an algorithmic order dict for the SDK."""
    order: dict = {
        "combo_type": "NORMAL",
        "order_type": effective_order_type,
        "time_in_force": "DAY",
        "support_trading_session": "CORE",
        "instrument_type": "EQUITY",
        "market": "US",
        "symbol": symbol,
        "side": side,
        "quantity": str(quantity),
        "algo_type": algo_type,
        "entrust_type": "QTY",
        "client_order_id": coid,
    }
    _add_optional_str(order, "algo_start_time", algo_start_time)
    _add_optional_str(order, "algo_end_time", algo_end_time)
    _add_optional_str(order, "max_target_percent", max_target_percent)
    _add_optional_str(order, "target_vol_percent", target_vol_percent)
    _add_optional_str(order, "limit_price", limit_price)
    return order


def _validate_algo_params(
    algo_type: str,
    max_target_percent: int | None,
    target_vol_percent: int | None,
) -> str | None:
    """Validate algo-specific required params. Returns error message or None."""
    if algo_type in ("TWAP", "VWAP") and max_target_percent is None:
        return "Validation error: max_target_percent is required for TWAP/VWAP (integer 1-20)"
    if algo_type == "POV" and target_vol_percent is None:
        return "Validation error: target_vol_percent is required for POV (integer 1-20)"
    return None


def register_stock_order_tools(
    mcp: FastMCP,
    sdk: WebullSDKClient,
    audit: AuditLogger,
    config: ServerConfig,
) -> None:
    """Register stock order tools."""

    # ------------------------------------------------------------------
    # Stock order tools
    # ------------------------------------------------------------------

    @mcp.tool(
        description=(
            "Place a stock order (single, non-combo). For combo orders use place_stock_combo_order.\n"
            "Account: stock/option account (Individual Cash, Individual Margin, IRA). Call get_account_list first.\n"
            "order_type by market:\n"
            "  US Stock: MARKET, LIMIT, STOP_LOSS, STOP_LOSS_LIMIT, TRAILING_STOP_LOSS\n"
            "  HK Stock: ENHANCED_LIMIT, AT_AUCTION, AT_AUCTION_LIMIT\n"
            "  CN Connect: LIMIT\n"
            "time_in_force by market:\n"
            "  US Stock: DAY, GTC\n"
            "  HK Stock: DAY, GTC\n"
            "  HK US Stock: DAY, GTC, GTD (requires expire_date)\n"
            "  CN Connect: DAY\n"
            "trading_session by market:\n"
            "  US Stock: CORE, ALL, NIGHT, ALL_DAY (overnight 8pm-8pm ET)\n"
            "  HK Stock / CN Connect: CORE only\n"
            "Returns: {client_order_id, order_id}"
        ),
    )
    async def place_stock_order(
        symbol: str,
        side: str,
        order_type: str,
        time_in_force: str,
        quantity: float,
        market: str = "US",
        account_id: Optional[str] = None,
        client_order_id: Optional[str] = None,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        entrust_type: str = "QTY",
        total_cash_amount: Optional[float] = None,
        trading_session: str = "CORE",
        extended_hours: bool = False,
        trailing_type: Optional[str] = None,
        trailing_stop_step: Optional[float] = None,
        expire_date: Optional[str] = None,
    ) -> str:
        """Place a single stock order (non-combo).

        Args:
            trailing_type: AMOUNT or PERCENTAGE. For TRAILING_STOP_LOSS orders.
            trailing_stop_step: Trailing spread. For PERCENTAGE, max 1 (0.01 = 1%).
            expire_date: GTD order expire date, format yyyy-MM-dd. Required when time_in_force=GTD.
        """
        audit.log_tool_call("place_stock_order", {"symbol": symbol, "side": side})

        # Auto-resolve account_id
        try:
            from webull_openapi_mcp.tools.trading.account import resolve_account_id
            account_id = await resolve_account_id(sdk, "stock", account_id)
        except ValueError as e:
            return f"Account error: {e}"

        # Build arguments dict for validation
        params: dict = {
            "symbol": symbol, "side": side, "order_type": order_type,
            "time_in_force": time_in_force, "quantity": quantity,
            "entrust_type": entrust_type, "trading_session": trading_session,
            "market": market,
        }
        if limit_price is not None:
            params["limit_price"] = limit_price
        if stop_price is not None:
            params["stop_price"] = stop_price

        try:
            validate_stock_order(params, config)
        except ValidationError as e:
            audit.log_validation_error("place_stock_order", e.message, params)
            return f"Validation error: {e.message}"

        try:
            validate_client_order_id(client_order_id)
        except ValidationError as e:
            return f"Validation error: {e.message}"

        coid = client_order_id or _generate_client_order_id()

        order = _build_stock_order({
            "coid": coid, "market": market, "symbol": symbol, "side": side,
            "order_type": order_type, "time_in_force": time_in_force,
            "entrust_type": entrust_type, "trading_session": trading_session,
            "quantity": quantity, "total_cash_amount": total_cash_amount,
            "limit_price": limit_price, "stop_price": stop_price,
            "extended_hours": extended_hours, "trailing_type": trailing_type,
            "trailing_stop_step": trailing_stop_step,
            "expire_date": expire_date,
        })

        audit.log_order_attempt(
            symbol=symbol, side=side, quantity=quantity,
            order_type=order_type, client_order_id=coid, account_id=account_id,
        )

        try:
            response = sdk.trade.order_v3.place_order(
                account_id=account_id, new_orders=[order],
            )
            data = extract_response_data(response)
            audit.log_order_result(
                client_order_id=coid, success=True,
                response=data if isinstance(data, dict) else {},
            )
            return prepend_disclaimer(_format_order_result(data if isinstance(data, dict) else {}))
        except Exception as e:
            audit.log_order_result(
                client_order_id=coid, success=False, response={"error": str(e)},
            )
            return handle_sdk_exception(e, "place_stock_order")

    @mcp.tool(
        description=(
            "Preview a stock order without submitting. Returns: estimated cost and fees.\n"
            "Account: stock/option account (Individual Cash, Individual Margin, IRA)."
        ),
    )
    async def preview_stock_order(
        account_id: str,
        symbol: str,
        side: str,
        order_type: str,
        time_in_force: str,
        quantity: float,
        market: str = "US",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        trading_session: str = "CORE",
    ) -> str:
        """Preview a stock order without submitting."""
        audit.log_tool_call("preview_stock_order", {"symbol": symbol, "side": side})

        order: dict = {
            "client_order_id": _generate_client_order_id(),
            "combo_type": "NORMAL",
            "instrument_type": "EQUITY",
            "market": market,
            "symbol": symbol,
            "order_type": order_type,
            "entrust_type": "QTY",
            "support_trading_session": trading_session,
            "time_in_force": time_in_force,
            "side": side,
            "quantity": str(quantity),
        }
        _add_optional_str(order, "limit_price", limit_price)
        _add_optional_str(order, "stop_price", stop_price)

        try:
            response = sdk.trade.order_v3.preview_order(
                account_id=account_id, preview_orders=[order],
            )
            data = extract_response_data(response)
            return prepend_disclaimer(format_order_preview(data if isinstance(data, dict) else {}))
        except Exception as e:
            return handle_sdk_exception(e, "preview_stock_order")

    @mcp.tool(
        description=(
            "Modify an existing stock order. For combo orders (US): pass orders array.\n"
            "For algo orders: can modify quantity, limit_price, max_target_percent (TWAP/VWAP), "
            "target_vol_percent (POV), algo_start_time, algo_end_time (HH:mm:ss ET).\n"
            "Returns: {client_order_id, order_id}"
        ),
    )
    async def replace_stock_order(
        account_id: str,
        client_order_id: Optional[str] = None,
        quantity: Optional[float] = None,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: Optional[str] = None,
        order_type: Optional[str] = None,
        expire_date: Optional[str] = None,
        trailing_type: Optional[str] = None,
        trailing_stop_step: Optional[float] = None,
        target_vol_percent: Optional[int] = None,
        max_target_percent: Optional[int] = None,
        algo_start_time: Optional[str] = None,
        algo_end_time: Optional[str] = None,
        orders: Optional[list[dict]] = None,
    ) -> str:
        """Modify an existing stock order.
        
        Args:
            trailing_type: AMOUNT or PERCENTAGE. For trailing stop orders.
            trailing_stop_step: Trailing spread. For PERCENTAGE, max 1 (0.01 = 1%).
            target_vol_percent: POV participation rate, integer 1-20.
            max_target_percent: TWAP/VWAP participation rate, integer 1-20.
            algo_start_time: US Eastern Time, HH:mm:ss (e.g. 09:30:00).
            algo_end_time: US Eastern Time, HH:mm:ss (e.g. 16:00:00).
        """
        audit.log_tool_call("replace_stock_order", {"account_id": account_id})

        try:
            validate_client_order_id(client_order_id)
        except ValidationError as e:
            return f"Validation error: {e.message}"

        if orders:
            modify_orders = [_build_modify_order(o) for o in orders]
        else:
            args = _collect_replace_args(
                client_order_id=client_order_id, quantity=quantity,
                limit_price=limit_price, stop_price=stop_price,
                time_in_force=time_in_force, order_type=order_type,
                expire_date=expire_date, trailing_type=trailing_type,
                trailing_stop_step=trailing_stop_step,
                target_vol_percent=target_vol_percent,
                max_target_percent=max_target_percent,
                algo_start_time=algo_start_time, algo_end_time=algo_end_time,
            )
            modify_orders = [_build_modify_order(args)]

        try:
            response = sdk.trade.order_v3.replace_order(
                account_id=account_id, modify_orders=modify_orders,
            )
            data = extract_response_data(response)
            return prepend_disclaimer(_format_order_result(data if isinstance(data, dict) else {}))
        except Exception as e:
            return handle_sdk_exception(e, "replace_stock_order")


def register_combo_order_tools(
    mcp: FastMCP,
    sdk: WebullSDKClient,
    audit: AuditLogger,
    config: ServerConfig,
) -> None:
    """Register combo stock order tools (US only)."""

    @mcp.tool(
        description=(
            "[US Only] Place a combo stock order. "
            "combo_type per leg: NORMAL, MASTER (triggers TP/SL), STOP_PROFIT, STOP_LOSS, OTO, OCO, OTOCO.\n"
            "Account: stock/option account. Call get_account_list first.\n"
            "Returns: {client_order_id, combo_order_id, order_id}"
        ),
    )
    async def place_stock_combo_order(
        account_id: str,
        orders: list[dict],
        client_combo_order_id: Optional[str] = None,
    ) -> str:
        """Place a combo stock order (OTO, OCO, OTOCO)."""
        audit.log_tool_call("place_stock_combo_order", {"account_id": account_id})

        for order in orders:
            try:
                validate_combo_order(order, config)
            except ValidationError as e:
                return f"Validation error: {e.message}"

        combo_id = client_combo_order_id or _generate_client_order_id()
        new_orders = [_build_combo_leg(order) for order in orders]

        audit.log_order_attempt(
            symbol=orders[0]["symbol"] if orders else "",
            side=orders[0]["side"] if orders else "",
            quantity=orders[0]["quantity"] if orders else 0,
            order_type="COMBO",
            client_order_id=combo_id,
            account_id=account_id,
        )

        try:
            response = sdk.trade.order_v3.place_order(
                account_id=account_id,
                new_orders=new_orders,
                client_combo_order_id=combo_id,
            )
            data = extract_response_data(response)
            audit.log_order_result(
                client_order_id=combo_id, success=True,
                response=data if isinstance(data, dict) else {},
            )
            return prepend_disclaimer(_format_order_result(data if isinstance(data, dict) else {}))
        except Exception as e:
            audit.log_order_result(
                client_order_id=combo_id, success=False, response={"error": str(e)},
            )
            return handle_sdk_exception(e, "place_stock_combo_order")


def register_algo_order_tools(
    mcp: FastMCP,
    sdk: WebullSDKClient,
    audit: AuditLogger,
    config: ServerConfig,
) -> None:
    """Register algorithmic order tools (US only)."""

    @mcp.tool(
        description=(
            "[US Only] Place an algorithmic order (TWAP, VWAP, POV).\n"
            "Only MARKET and LIMIT order types supported.\n"
            "TWAP/VWAP require max_target_percent (1-20). POV requires target_vol_percent (1-20).\n"
            "algo_start_time/algo_end_time: US Eastern Time, HH:mm:ss format (e.g. 09:30:00, 16:00:00).\n"
            "Returns: {client_order_id, order_id}"
        ),
    )
    async def place_algo_order(
        account_id: str,
        symbol: str,
        side: str,
        quantity: float,
        algo_type: str,
        client_order_id: Optional[str] = None,
        order_type: Optional[str] = None,
        limit_price: Optional[float] = None,
        algo_start_time: Optional[str] = None,
        algo_end_time: Optional[str] = None,
        target_vol_percent: Optional[int] = None,
        max_target_percent: Optional[int] = None,
    ) -> str:
        """Place an algorithmic order (TWAP, VWAP, POV).
        
        Args:
            algo_start_time: Start time in US Eastern Time, HH:mm:ss (e.g. 09:30:00). Must be later than current time.
            algo_end_time: End time in US Eastern Time, HH:mm:ss (e.g. 16:00:00).
            target_vol_percent: Max participation rate of market volume for POV. Integer 1-20.
            max_target_percent: Target participation rate for TWAP/VWAP. Integer 1-20.
        """
        audit.log_tool_call("place_algo_order", {"symbol": symbol, "algo_type": algo_type})

        effective_order_type = order_type or "LIMIT"
        if effective_order_type not in ("MARKET", "LIMIT"):
            return f"Validation error: algo orders only support MARKET or LIMIT order_type, got '{effective_order_type}'"

        params: dict = {"side": side, "order_type": effective_order_type, "quantity": quantity, "algo_type": algo_type}
        try:
            validate_algo_order(params, config)
        except ValidationError as e:
            return f"Validation error: {e.message}"

        try:
            validate_client_order_id(client_order_id)
        except ValidationError as e:
            return f"Validation error: {e.message}"

        param_error = _validate_algo_params(algo_type, max_target_percent, target_vol_percent)
        if param_error:
            return param_error

        coid = client_order_id or _generate_client_order_id()

        order = _build_algo_order(
            coid=coid, symbol=symbol, side=side, quantity=quantity,
            algo_type=algo_type, effective_order_type=effective_order_type,
            limit_price=limit_price, algo_start_time=algo_start_time,
            algo_end_time=algo_end_time, target_vol_percent=target_vol_percent,
            max_target_percent=max_target_percent,
        )

        audit.log_order_attempt(
            symbol=symbol, side=side, quantity=quantity,
            order_type=f"ALGO_{algo_type}", client_order_id=coid,
            account_id=account_id,
        )

        try:
            response = sdk.trade.order_v3.place_order(
                account_id=account_id, new_orders=[order],
            )
            data = extract_response_data(response)
            audit.log_order_result(
                client_order_id=coid, success=True,
                response=data if isinstance(data, dict) else {},
            )
            return prepend_disclaimer(_format_order_result(data if isinstance(data, dict) else {"client_order_id": coid}))
        except Exception as e:
            audit.log_order_result(
                client_order_id=coid, success=False, response={"error": str(e)},
            )
            return handle_sdk_exception(e, "place_algo_order")
