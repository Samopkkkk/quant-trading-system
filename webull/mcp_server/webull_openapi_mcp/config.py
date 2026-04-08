"""Configuration management for Webull MCP Server."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

from webull_openapi_mcp.errors import ConfigError

logger = logging.getLogger(__name__)


@dataclass
class ServerConfig:
    """Immutable server configuration loaded from environment variables / .env file."""

    app_key: str
    app_secret: str
    region_id: str = "us"
    environment: str = "uat"  # "uat" | "prod"
    # Market-specific notional limits (by currency)
    max_order_notional_usd: float = 10_000.0  # For US market
    max_order_notional_hkd: float = 80_000.0  # For HK market
    max_order_notional_cnh: float = 70_000.0  # For CN market
    max_order_quantity: float = 1_000.0
    symbol_whitelist: list[str] | None = None
    audit_log_file: str | None = None
    token_dir: str | None = None  # Passed to SDK's api_client.set_token_dir(), None uses SDK's built-in priority resolution
    toolsets: frozenset[str] | None = None  # None = all toolsets enabled
    
    # Legacy property for backward compatibility
    @property
    def max_order_notional(self) -> float:
        """Return USD limit for backward compatibility."""
        return self.max_order_notional_usd
    
    def get_max_notional_for_market(self, market: str | None) -> tuple[float, str]:
        """Get max notional limit and currency for a specific market.
        
        Parameters
        ----------
        market
            Market code: US, HK, or CN
            
        Returns
        -------
        tuple[float, str]
            (max_notional, currency) for the market
        """
        if market == "HK":
            return (self.max_order_notional_hkd, "HKD")
        elif market == "CN":
            return (self.max_order_notional_cnh, "CNH")
        else:  # US or default
            return (self.max_order_notional_usd, "USD")


def _parse_whitelist(raw: str | None) -> list[str] | None:
    """Parse comma-separated whitelist string into a list, or None if empty."""
    if not raw or not raw.strip():
        return None
    items = [s.strip() for s in raw.split(",") if s.strip()]
    return items if items else None


def _parse_toolsets(raw: str | None) -> frozenset[str] | None:
    """Parse comma-separated toolsets string into a frozenset, or None if empty."""
    if not raw or not raw.strip():
        return None
    items = frozenset(s.strip() for s in raw.split(",") if s.strip())
    return items if items else None


def _parse_float(raw: str | None, default: float) -> float:
    """Parse a string to float, returning *default* on None or invalid input."""
    if raw is None:
        return default
    try:
        return float(raw)
    except (ValueError, TypeError):
        return default


def load_config(env_file: str | None = None) -> ServerConfig:
    """Load configuration from environment variables / .env file.

    Parameters
    ----------
    env_file:
        Optional path to a ``.env`` file.  When provided the file is loaded
        **before** reading ``os.environ`` so that file values act as defaults
        that real env-vars can override (``python-dotenv`` default behaviour).
    """
    if env_file is not None:
        load_dotenv(env_file, override=False)
    else:
        # Try loading a .env in the current directory as a convenience default
        load_dotenv(override=False)

    app_key = os.environ.get("WEBULL_APP_KEY", "")
    app_secret = os.environ.get("WEBULL_APP_SECRET", "")
    region_id = os.environ.get("WEBULL_REGION_ID", "us")
    environment = os.environ.get("WEBULL_ENVIRONMENT", "uat")
    # Market-specific notional limits
    max_order_notional_usd = _parse_float(os.environ.get("WEBULL_MAX_ORDER_NOTIONAL_USD"), 10_000.0)
    max_order_notional_hkd = _parse_float(os.environ.get("WEBULL_MAX_ORDER_NOTIONAL_HKD"), 80_000.0)
    max_order_notional_cnh = _parse_float(os.environ.get("WEBULL_MAX_ORDER_NOTIONAL_CNH"), 70_000.0)
    max_order_quantity = _parse_float(os.environ.get("WEBULL_MAX_ORDER_QUANTITY"), 1_000.0)
    symbol_whitelist = _parse_whitelist(os.environ.get("WEBULL_SYMBOL_WHITELIST"))
    audit_log_file = os.environ.get("WEBULL_AUDIT_LOG_FILE") or None
    token_dir = os.environ.get("WEBULL_TOKEN_DIR") or None
    toolsets = _parse_toolsets(os.environ.get("WEBULL_TOOLSETS"))

    return ServerConfig(
        app_key=app_key,
        app_secret=app_secret,
        region_id=region_id,
        environment=environment,
        max_order_notional_usd=max_order_notional_usd,
        max_order_notional_hkd=max_order_notional_hkd,
        max_order_notional_cnh=max_order_notional_cnh,
        max_order_quantity=max_order_quantity,
        symbol_whitelist=symbol_whitelist,
        audit_log_file=audit_log_file,
        token_dir=token_dir,
        toolsets=toolsets,
    )


def validate_config(config: ServerConfig) -> None:
    """Validate that required credentials are present.

    Raises
    ------
    ConfigError
        If ``app_key`` or ``app_secret`` is empty / missing.
    """
    if not config.app_key:
        raise ConfigError(
            "WEBULL_APP_KEY is required but not set. "
            "Provide it via environment variable or .env file."
        )
    if not config.app_secret:
        raise ConfigError(
            "WEBULL_APP_SECRET is required but not set. "
            "Provide it via environment variable or .env file."
        )
    
    # Validate region configuration
    from webull_openapi_mcp.region_config import get_region_config, SUPPORTED_REGIONS
    from webull_openapi_mcp.errors import UnsupportedRegionError
    
    try:
        region_config = get_region_config(config.region_id)
        logger.info(
            "Region configuration validated: region=%s, environment=%s",
            region_config.region_id,
            config.environment,
        )
    except UnsupportedRegionError as e:
        raise ConfigError(str(e)) from e
