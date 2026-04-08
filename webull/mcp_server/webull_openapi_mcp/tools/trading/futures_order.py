"""Futures order tools for Webull MCP Server.

Provides fine-grained futures order tools:
- place_futures_order: Place a futures order
- replace_futures_order: Modify existing futures order

Note: Uses order_v3 SDK API (OrderOperationV3).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional

from webull_openapi_mcp.errors import ValidationError, handle_sdk_exception
from webull_openapi_mcp.formatters import prepend_disclaimer, extract_response_data
from webull_openapi_mcp.guards import validate_client_order_id, validate_stock_order

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
    if "order_id" in data:
        result["order_id"] = data["order_id"]

    if not result:
        return str(data)

    lines = [f"{k}: {v}" for k, v in result.items()]
    return "\n".join(lines)


def _build_futures_order(
    symbol: str,
    side: str,
    order_type: str,
    time_in_force: str,
    quantity: float,
    coid: str,
    limit_price: float | None,
    stop_price: float | None,
) -> dict:
    """Build the futures order dict for the SDK."""
    order: dict = {
        "combo_type": "NORMAL",
        "instrument_type": "FUTURES",
        "market": "US",
        "symbol": symbol,
        "side": side,
        "order_type": order_type,
        "time_in_force": time_in_force,
        "quantity": str(quantity),
        "entrust_type": "QTY",
        "client_order_id": coid,
    }
    if limit_price is not None:
        order["limit_price"] = str(limit_price)
    if stop_price is not None:
        order["stop_price"] = str(stop_price)
    return order


def register_futures_order_tools(
    mcp: FastMCP,
    sdk: WebullSDKClient,
    audit: AuditLogger,
    config: ServerConfig,
) -> None:
    """Register futures order tools."""

    @mcp.tool(
        description=(
            "[US Only] Place a futures order. QTY only.\n"
            "Account: Futures account. Call get_account_list first.\n"
            "order_type: MARKET, LIMIT, STOP_LOSS, STOP_LOSS_LIMIT, TRAILING_STOP_LOSS.\n"
            "Returns: {client_order_id, order_id}"
        ),
    )
    async def place_futures_order(
        symbol: str,
        side: str,
        order_type: str,
        time_in_force: str,
        quantity: float,
        account_id: Optional[str] = None,
        client_order_id: Optional[str] = None,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> str:
        """Place a futures order."""
        audit.log_tool_call("place_futures_order", {"symbol": symbol, "side": side})

        # Auto-resolve account_id
        try:
            from webull_openapi_mcp.tools.trading.account import resolve_account_id
            account_id = await resolve_account_id(sdk, "futures", account_id)
        except ValueError as e:
            return f"Account error: {e}"

        try:
            validate_client_order_id(client_order_id)
        except Exception as e:
            return f"Validation error: {e}"

        params: dict = {
            "side": side, "order_type": order_type, "time_in_force": time_in_force,
            "quantity": quantity, "symbol": symbol,
        }
        if limit_price is not None:
            params["limit_price"] = limit_price
        if stop_price is not None:
            params["stop_price"] = stop_price
        try:
            validate_stock_order(params, config)
        except ValidationError as e:
            return f"Validation error: {e.message}"

        coid = client_order_id or _generate_client_order_id()

        order = _build_futures_order(
            symbol=symbol, side=side, order_type=order_type,
            time_in_force=time_in_force, quantity=quantity, coid=coid,
            limit_price=limit_price, stop_price=stop_price,
        )

        audit.log_order_attempt(
            symbol=symbol, side=side, quantity=quantity,
            order_type=order_type, client_order_id=coid,
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
            return prepend_disclaimer(_format_order_result(data if isinstance(data, dict) else {}))
        except Exception as e:
            audit.log_order_result(
                client_order_id=coid, success=False, response={"error": str(e)},
            )
            return handle_sdk_exception(e, "place_futures_order")

    @mcp.tool(
        description=(
            "[US Only] Modify an existing futures order. "
            "Market orders: only quantity modifiable. "
            "Returns: {client_order_id, order_id}"
        ),
    )
    async def replace_futures_order(
        account_id: str,
        client_order_id: str,
        quantity: Optional[float] = None,
        limit_price: Optional[float] = None,
        order_type: Optional[str] = None,
    ) -> str:
        """Modify an existing futures order."""
        audit.log_tool_call("replace_futures_order", {"account_id": account_id, "client_order_id": client_order_id})

        try:
            validate_client_order_id(client_order_id)
        except Exception as e:
            return f"Validation error: {e}"

        modify_order: dict = {"client_order_id": client_order_id}
        if quantity is not None:
            modify_order["quantity"] = str(quantity)
        if limit_price is not None:
            modify_order["limit_price"] = str(limit_price)
        if order_type is not None:
            modify_order["order_type"] = order_type

        try:
            response = sdk.trade.order_v3.replace_order(
                account_id=account_id, modify_orders=[modify_order],
            )
            data = extract_response_data(response)
            return prepend_disclaimer(_format_order_result(data if isinstance(data, dict) else {}))
        except Exception as e:
            return handle_sdk_exception(e, "replace_futures_order")
