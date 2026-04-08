# Feature: webull-mcp-server, Property 4: Enum Field Validation - Equity Order
# Feature: webull-mcp-server, Property 5: Quantity and Notional Value Boundary Validation
# Feature: webull-mcp-server, Property 6: Order Type and Price Field Consistency
# Feature: webull-mcp-server, Property 7: Symbol Whitelist Filtering
# Feature: webull-mcp-server, Property 8: Option Order Comprehensive Validation
"""Property-based tests for order validation guards.

Validates: Requirements 12.2-12.14, 13.1-13.5, 8.10-8.12, 9.4-9.6
"""

from __future__ import annotations

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from webull_openapi_mcp.config import ServerConfig
from webull_openapi_mcp.constants import (
    STRATEGY_LEG_COUNT,
    VALID_OPTION_ORDER_TYPES,
    VALID_OPTION_TIF,
    VALID_SIDES,
)
from webull_openapi_mcp.errors import RegionValidationError, ValidationError
from webull_openapi_mcp.guards import OrderValidator
from webull_openapi_mcp.region_config import US_REGION_CONFIG, HK_REGION_CONFIG


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config(**overrides) -> ServerConfig:
    """Build a ServerConfig with sensible defaults."""
    defaults = dict(
        app_key="test_key",
        app_secret="test_secret",
        region_id="us",
        max_order_notional_usd=10_000.0,
        max_order_notional_hkd=80_000.0,
        max_order_notional_cnh=70_000.0,
        max_order_quantity=1_000.0,
    )
    defaults.update(overrides)
    return ServerConfig(**defaults)


def _us_validator(**config_overrides) -> OrderValidator:
    """Create a US region validator."""
    return OrderValidator(US_REGION_CONFIG, _config(**config_overrides))


def _valid_params(**overrides) -> dict:
    """Return a minimal valid stock order params dict (MARKET)."""
    base = dict(
        symbol="AAPL",
        side="BUY",
        quantity=10,
        order_type="MARKET",
        time_in_force="DAY",
    )
    base.update(overrides)
    return base


def _valid_option_params(**overrides) -> dict:
    """Return a minimal valid option order params dict (LIMIT / SINGLE)."""
    base = dict(
        side="BUY",
        order_type="LIMIT",
        time_in_force="DAY",
        limit_price=5.00,
    )
    base.update(overrides)
    return base


def _valid_strategy_params(**overrides) -> dict:
    """Return a minimal valid option strategy order params dict."""
    base = dict(
        strategy="SINGLE",
        order_type="LIMIT",
        time_in_force="DAY",
        limit_price=5.00,
        legs=[_make_leg()],
    )
    base.update(overrides)
    return base


def _make_leg(**overrides) -> dict:
    """Return a single valid option leg dict."""
    base = {
        "symbol": "AAPL230120C00150000",
        "side": "BUY",
        "quantity": 1,
        "option_type": "CALL",
        "strike_price": 150.0,
        "option_expire_date": "2023-01-20",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Random text that won't accidentally land in a valid enum set.
_random_str = st.text(min_size=1, max_size=30)


# ---------------------------------------------------------------------------
# Property 4: Enum Field Validation - Equity Order
# **Validates: Requirements 12.2, 12.3, 12.4, 12.5, 12.6, 8.10, 8.11, 8.12**
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(side=_random_str)
def test_invalid_side_rejected(side: str):
    """Any side value not in VALID_SIDES must cause ValidationError."""
    assume(side not in VALID_SIDES)
    with pytest.raises(ValidationError):
        _us_validator().validate_stock_order(_valid_params(side=side))


@settings(max_examples=100)
@given(order_type=_random_str)
def test_invalid_order_type_rejected(order_type: str):
    """Any order_type not in US region valid order types must cause error."""
    assume(order_type not in US_REGION_CONFIG.valid_order_types)
    with pytest.raises((ValidationError, RegionValidationError)):
        _us_validator().validate_stock_order(_valid_params(order_type=order_type))


@settings(max_examples=100)
@given(tif=_random_str)
def test_invalid_time_in_force_rejected(tif: str):
    """Any time_in_force not in US region valid values must cause error."""
    assume(tif not in US_REGION_CONFIG.valid_time_in_force)
    with pytest.raises((ValidationError, RegionValidationError)):
        _us_validator().validate_stock_order(_valid_params(time_in_force=tif))


@settings(max_examples=100)
@given(session=_random_str)
def test_invalid_trading_session_rejected(session: str):
    """Any trading_session not in US region valid values must cause error."""
    assume(session not in US_REGION_CONFIG.valid_trading_sessions)
    with pytest.raises((ValidationError, RegionValidationError)):
        _us_validator().validate_stock_order(_valid_params(trading_session=session))


# ---------------------------------------------------------------------------
# Property 5: Quantity and Notional Value Boundary Validation
# **Validates: Requirements 12.7, 12.8, 12.9**
# ---------------------------------------------------------------------------

# Positive floats for config limits
_pos_limit = st.floats(min_value=1.0, max_value=1e9, allow_nan=False, allow_infinity=False)


@settings(max_examples=100)
@given(
    quantity=st.floats(max_value=0.0, allow_nan=False, allow_infinity=False),
)
def test_non_positive_quantity_rejected(quantity: float):
    """quantity <= 0 must always be rejected."""
    with pytest.raises(ValidationError):
        _us_validator().validate_stock_order(_valid_params(quantity=quantity))


@settings(max_examples=100)
@given(
    max_qty=_pos_limit,
    extra=st.floats(min_value=0.001, max_value=1e6, allow_nan=False, allow_infinity=False),
)
def test_quantity_exceeding_max_rejected(max_qty: float, extra: float):
    """quantity > max_order_quantity must be rejected."""
    quantity = max_qty + extra
    with pytest.raises(ValidationError):
        _us_validator(max_order_quantity=max_qty).validate_stock_order(
            _valid_params(quantity=quantity)
        )


@settings(max_examples=100)
@given(
    quantity=st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    price=st.floats(min_value=1.0, max_value=1e6, allow_nan=False, allow_infinity=False),
    max_notional=st.floats(min_value=1.0, max_value=1e6, allow_nan=False, allow_infinity=False),
)
def test_qty_mode_notional_exceeded_rejected(quantity: float, price: float, max_notional: float):
    """qty * price > max_order_notional must be rejected."""
    assume(quantity * price > max_notional)
    with pytest.raises(ValidationError):
        _us_validator(max_order_notional_usd=max_notional, max_order_quantity=1e9).validate_stock_order(
            _valid_params(quantity=quantity, limit_price=price, order_type="LIMIT")
        )


# ---------------------------------------------------------------------------
# Property 6: Order Type and Price Field Consistency
# **Validates: Requirements 12.10, 12.11, 12.12, 12.13**
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(data=st.data())
def test_limit_missing_price_rejected(data):
    """LIMIT order without limit_price must be rejected."""
    with pytest.raises(ValidationError):
        _us_validator().validate_stock_order(_valid_params(order_type="LIMIT", limit_price=None))


@settings(max_examples=100)
@given(data=st.data())
def test_stop_loss_missing_stop_price_rejected(data):
    """STOP_LOSS order without stop_price must be rejected."""
    with pytest.raises(ValidationError):
        _us_validator().validate_stock_order(_valid_params(order_type="STOP_LOSS", stop_price=None))


@settings(max_examples=100)
@given(has_price=st.booleans(), has_stop_price=st.booleans())
def test_stop_loss_limit_missing_either_price_rejected(has_price: bool, has_stop_price: bool):
    """STOP_LOSS_LIMIT missing limit_price or stop_price (or both) must be rejected."""
    assume(not has_price or not has_stop_price)  # at least one missing
    params = _valid_params(
        order_type="STOP_LOSS_LIMIT",
        limit_price=100.0 if has_price else None,
        stop_price=95.0 if has_stop_price else None,
    )
    with pytest.raises(ValidationError):
        _us_validator().validate_stock_order(params)


# ---------------------------------------------------------------------------
# Property 7: Symbol Whitelist Filtering
# **Validates: Requirements 12.14**
# ---------------------------------------------------------------------------

_symbol_str = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=10,
)


@settings(max_examples=100)
@given(
    symbol=_symbol_str,
    whitelist=st.lists(_symbol_str, min_size=1, max_size=10),
)
def test_symbol_not_in_whitelist_rejected(symbol: str, whitelist: list[str]):
    """Symbol not in a non-empty whitelist must be rejected."""
    assume(symbol not in whitelist)
    with pytest.raises(ValidationError):
        _us_validator(symbol_whitelist=whitelist).validate_stock_order(
            _valid_params(symbol=symbol)
        )


@settings(max_examples=100)
@given(
    whitelist=st.lists(_symbol_str, min_size=1, max_size=10),
)
def test_symbol_in_whitelist_passes(whitelist: list[str]):
    """Symbol present in the whitelist must pass the whitelist check."""
    symbol = whitelist[0]
    _us_validator(symbol_whitelist=whitelist).validate_stock_order(
        _valid_params(symbol=symbol)
    )


# ---------------------------------------------------------------------------
# Property 8: Option Order Comprehensive Validation
# **Validates: Requirements 13.1, 13.2, 13.3, 13.4, 13.5, 9.4, 9.5, 9.6**
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(order_type=_random_str)
def test_option_invalid_order_type_rejected(order_type: str):
    """Option order_type not in VALID_OPTION_ORDER_TYPES must be rejected."""
    assume(order_type not in VALID_OPTION_ORDER_TYPES)
    with pytest.raises(ValidationError):
        _us_validator().validate_option_order(_valid_option_params(order_type=order_type))


@settings(max_examples=100)
@given(tif=_random_str)
def test_option_invalid_tif_rejected(tif: str):
    """Option time_in_force not in VALID_OPTION_TIF must be rejected."""
    assume(tif not in VALID_OPTION_TIF)
    with pytest.raises(ValidationError):
        _us_validator().validate_option_order(_valid_option_params(time_in_force=tif))


@settings(max_examples=100)
@given(data=st.data())
def test_option_limit_missing_limit_price_rejected(data):
    """LIMIT option order without limit_price must be rejected."""
    with pytest.raises(ValidationError):
        _us_validator().validate_option_order(
            _valid_option_params(order_type="LIMIT", limit_price=None)
        )


@settings(max_examples=100)
@given(
    order_type=st.sampled_from(["STOP_LOSS", "STOP_LOSS_LIMIT"]),
)
def test_option_stop_types_missing_stop_price_rejected(order_type: str):
    """STOP_LOSS or STOP_LOSS_LIMIT option order without stop_price must be rejected."""
    with pytest.raises(ValidationError):
        _us_validator().validate_option_order(
            _valid_option_params(order_type=order_type, stop_price=None)
        )


@settings(max_examples=100)
@given(
    strategy=st.sampled_from(sorted(STRATEGY_LEG_COUNT.keys())),
    leg_count=st.integers(min_value=0, max_value=10),
)
def test_option_leg_count_out_of_range_rejected(strategy: str, leg_count: int):
    """Leg count outside STRATEGY_LEG_COUNT[strategy] range must be rejected."""
    min_legs, max_legs = STRATEGY_LEG_COUNT[strategy]
    assume(leg_count < min_legs or leg_count > max_legs)
    with pytest.raises(ValidationError):
        _us_validator().validate_option_strategy_order(
            _valid_strategy_params(strategy=strategy, legs=[_make_leg()] * leg_count)
        )
