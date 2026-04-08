"""Futures market data tools for Webull MCP Server.

Provides: get_futures_tick, get_futures_snapshot, get_futures_depth,
          get_futures_bars, get_futures_footprint.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from webull_openapi_mcp.errors import handle_sdk_exception
from webull_openapi_mcp.formatters import (
    extract_response_data,
    format_futures_bars,
    format_futures_depth,
    format_futures_footprint,
    format_futures_snapshot,
    format_futures_tick,
    prepend_disclaimer,
)

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from webull_openapi_mcp.audit import AuditLogger
    from webull_openapi_mcp.config import ServerConfig
    from webull_openapi_mcp.sdk_client import WebullSDKClient


def _build_kwargs(base: dict[str, Any], **optional: Any) -> dict[str, Any]:
    """Build kwargs dict, adding only non-None / truthy optional values."""
    for key, value in optional.items():
        if value is not None and value is not False:
            base[key] = value
    return base


def register_futures_market_data_tools(
    mcp: FastMCP,
    sdk: WebullSDKClient,
    audit: AuditLogger,
    config: ServerConfig,
) -> None:
    """Register futures market data tools."""

    @mcp.tool(
        description=(
            "Get futures tick-by-tick trade data. "
            "Returns: time, price, volume, side."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_futures_tick(
        symbol: str,
        category: str = "US_FUTURES",
        count: int = 200,
    ) -> str:
        """Fetch tick-by-tick trade data for a futures symbol."""
        audit.log_tool_call("get_futures_tick", {"symbol": symbol})
        try:
            kwargs = _build_kwargs(
                {"symbol": symbol, "category": category},
                count=str(count) if count != 200 else None,
            )
            data = extract_response_data(sdk.data.futures_market_data.get_futures_tick(**kwargs))
            return prepend_disclaimer(format_futures_tick(data))
        except Exception as e:
            return handle_sdk_exception(e, "get_futures_tick", config.region_id)

    @mcp.tool(
        description=(
            "Get futures real-time snapshot. "
            "Returns: symbol, price, change, change_ratio, volume, "
            "open_interest, settle_price, bid, ask."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_futures_snapshot(
        symbols: str,
        category: str = "US_FUTURES",
    ) -> str:
        """Fetch real-time futures snapshot for one or more symbols."""
        audit.log_tool_call("get_futures_snapshot", {"symbols": symbols})
        try:
            sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
            data = extract_response_data(
                sdk.data.futures_market_data.get_futures_snapshot(symbols=sym_list, category=category)
            )
            return prepend_disclaimer(format_futures_snapshot(data))
        except Exception as e:
            return handle_sdk_exception(e, "get_futures_snapshot", config.region_id)

    @mcp.tool(
        description=(
            "Get futures order book depth. "
            "Returns: symbol, bids, asks."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_futures_depth(
        symbol: str,
        category: str = "US_FUTURES",
        depth: Optional[int] = None,
    ) -> str:
        """Fetch order book depth for a futures symbol."""
        audit.log_tool_call("get_futures_depth", {"symbol": symbol})
        try:
            kwargs = _build_kwargs(
                {"symbol": symbol, "category": category},
                depth=depth,
            )
            data = extract_response_data(sdk.data.futures_market_data.get_futures_depth(**kwargs))
            return prepend_disclaimer(format_futures_depth(data))
        except Exception as e:
            return handle_sdk_exception(e, "get_futures_depth", config.region_id)

    @mcp.tool(
        description=(
            "Get futures OHLCV bars in batch. "
            "Returns: time, open, high, low, close, volume."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_futures_bars(
        symbols: str,
        category: str = "US_FUTURES",
        timespan: str = "D",
        count: int = 200,
        real_time_required: bool = False,
    ) -> str:
        """Batch fetch historical OHLCV bar data for multiple futures symbols."""
        audit.log_tool_call("get_futures_bars", {"symbols": symbols})
        try:
            sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
            kwargs = _build_kwargs(
                {"symbols": sym_list, "category": category, "timespan": timespan},
                count=str(count) if count != 200 else None,
                real_time_required=real_time_required,
            )
            data = extract_response_data(sdk.data.futures_market_data.get_futures_history_bars(**kwargs))
            return prepend_disclaimer(format_futures_bars(data))
        except Exception as e:
            return handle_sdk_exception(e, "get_futures_bars", config.region_id)

    @mcp.tool(
        description=(
            "Get futures large order footprint (order flow). "
            "Returns: time, trading_session, total, delta, buy_total, sell_total."
        ),
        annotations={"readOnlyHint": True},
    )
    async def get_futures_footprint(
        symbols: str,
        category: str = "US_FUTURES",
        timespan: str = "M1",
        count: int = 200,
        real_time_required: bool = False,
        trading_sessions: Optional[str] = None,
    ) -> str:
        """Fetch footprint (large order) data for futures symbols."""
        audit.log_tool_call("get_futures_footprint", {"symbols": symbols})
        try:
            sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
            kwargs = _build_kwargs(
                {"symbols": sym_list, "category": category, "timespan": timespan},
                count=str(count) if count != 200 else None,
                real_time_required=real_time_required,
                trading_sessions=trading_sessions,
            )
            data = extract_response_data(sdk.data.futures_market_data.get_futures_footprint(**kwargs))
            return prepend_disclaimer(format_futures_footprint(data))
        except Exception as e:
            return handle_sdk_exception(e, "get_futures_footprint", config.region_id)
