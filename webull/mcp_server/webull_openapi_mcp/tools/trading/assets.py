"""Assets tools for Webull MCP Server.

Provides: get_account_balance, get_account_positions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from webull_openapi_mcp.errors import handle_sdk_exception
from webull_openapi_mcp.formatters import (
    extract_response_data,
    format_account_balance,
    format_positions,
    prepend_disclaimer,
)

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from webull_openapi_mcp.audit import AuditLogger
    from webull_openapi_mcp.sdk_client import WebullSDKClient


def register_assets_tools(
    mcp: FastMCP,
    sdk: WebullSDKClient,
    audit: AuditLogger,
) -> None:
    """Register account balance and position tools."""

    @mcp.tool(
        description=(
            "Get account balance. "
            "Returns: net_liquidation, buying_power, cash_balance, "
            "market_value, unrealized_pnl, realized_pnl."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_account_balance(account_id: str) -> str:
        """Get account balance information."""
        audit.log_tool_call("get_account_balance", {"account_id": account_id})
        try:
            response = sdk.trade.account_v2.get_account_balance(account_id)
            data = extract_response_data(response)
            return prepend_disclaimer(format_account_balance(data))
        except Exception as e:
            return handle_sdk_exception(e, "get_account_balance")

    @mcp.tool(
        description=(
            "Get account positions. "
            "Returns: symbol, quantity, side, avg_cost, last_price, "
            "market_value, unrealized_pnl, realized_pnl."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_account_positions(account_id: str) -> str:
        """Get account positions list."""
        audit.log_tool_call("get_account_positions", {"account_id": account_id})
        try:
            response = sdk.trade.account_v2.get_account_position(account_id)
            data = extract_response_data(response)
            return prepend_disclaimer(format_positions(data))
        except Exception as e:
            return handle_sdk_exception(e, "get_account_positions")
