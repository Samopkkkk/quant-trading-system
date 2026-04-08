"""Trading API tools for Webull MCP Server.

Provides register_*_tools functions for trading operations:
- Instrument: Query tradable instruments
- Account: Account information
- Assets: Account balance and positions
- Order: Universal cancel order
- Stock Order: Stock order operations
- Option Order: Single-leg + multi-leg option order operations
- Futures Order: Futures order operations
- Crypto Order: Cryptocurrency order operations
- Event Order: Event contract order operations
- Query Order: Order history and status queries
"""

from webull_openapi_mcp.tools.trading.account import register_account_tools, resolve_account_id
from webull_openapi_mcp.tools.trading.assets import register_assets_tools
from webull_openapi_mcp.tools.trading.order import register_order_tools
from webull_openapi_mcp.tools.trading.instrument import register_instrument_tools
from webull_openapi_mcp.tools.trading.stock_order import (
    register_stock_order_tools,
    register_combo_order_tools,
    register_algo_order_tools,
)
from webull_openapi_mcp.tools.trading.option_order import (
    register_option_single_tools,
    register_option_strategy_tools,
)
from webull_openapi_mcp.tools.trading.futures_order import register_futures_order_tools
from webull_openapi_mcp.tools.trading.crypto_order import register_crypto_order_tools
from webull_openapi_mcp.tools.trading.event_order import register_event_order_tools

__all__ = [
    # Account
    "register_account_tools",
    "resolve_account_id",
    # Assets
    "register_assets_tools",
    # Order (cancel + query)
    "register_order_tools",
    # Instrument
    "register_instrument_tools",
    # Stock
    "register_stock_order_tools",
    "register_combo_order_tools",
    "register_algo_order_tools",
    # Option single-leg + strategy
    "register_option_single_tools",
    "register_option_strategy_tools",
    # Futures
    "register_futures_order_tools",
    # Crypto
    "register_crypto_order_tools",
    # Event
    "register_event_order_tools",
]
