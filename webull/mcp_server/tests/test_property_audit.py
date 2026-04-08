# Feature: webull-mcp-server, Property 9: Audit Log JSON Format and Event Completeness
# Feature: webull-mcp-server, Property 10: Audit Log Price Masking
# Feature: webull-mcp-server, Property 11: Credentials Not Leaked
"""Property-based tests for audit logging.

Validates: Requirements 15.1, 15.5, 15.6, 15.7, 15.8, 15.9, 2.3, 15.10
"""

from __future__ import annotations

import json
import logging

from hypothesis import given, settings
from hypothesis import strategies as st

from webull_openapi_mcp.audit import AuditLogger
from webull_openapi_mcp.config import ServerConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config(**overrides) -> ServerConfig:
    defaults = dict(app_key="test_key", app_secret="test_secret")
    defaults.update(overrides)
    return ServerConfig(**defaults)


def _capture_lines(audit: AuditLogger) -> list[str]:
    """Attach a handler that collects every emitted log line into a list."""
    lines: list[str] = []

    class _Capture(logging.Handler):  # NOSONAR - test-only log capture handler
        def emit(self, record: logging.LogRecord) -> None:
            lines.append(record.getMessage())

    audit._logger.addHandler(_Capture())
    return lines


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_safe_text = st.text(min_size=1, max_size=50)
_safe_key = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
    min_size=1,
    max_size=20,
)
_json_values = st.recursive(
    st.one_of(
        st.none(),
        st.booleans(),
        st.integers(min_value=-10_000, max_value=10_000),
        st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
        st.text(min_size=0, max_size=30),
    ),
    lambda children: st.one_of(
        st.lists(children, max_size=3),
        st.dictionaries(_safe_key, children, max_size=3),
    ),
    max_leaves=10,
)
_params_strategy = st.dictionaries(_safe_key, _json_values, min_size=0, max_size=5)


# ---------------------------------------------------------------------------
# Property 9: Audit Log JSON Format and Event Completeness
# **Validates: Requirements 15.1, 15.5, 15.6, 15.7, 15.8**
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(tool_name=_safe_text, params=_params_strategy)
def test_tool_call_json_format_and_fields(tool_name: str, params: dict):
    """TOOL_CALL output is valid JSON with event, timestamp, tool, params."""
    audit = AuditLogger(_config())
    lines = _capture_lines(audit)
    audit.log_tool_call(tool_name, params)

    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["event"] == "TOOL_CALL"
    assert "timestamp" in data
    assert data["tool"] == tool_name
    assert "params" in data


@settings(max_examples=100)
@given(
    symbol=_safe_text,
    side=st.sampled_from(["BUY", "SELL"]),
    quantity=st.floats(min_value=0.01, max_value=1e6, allow_nan=False, allow_infinity=False),
    order_type=_safe_text,
    client_order_id=_safe_text,
    account_id=_safe_text,
)
def test_order_attempt_json_format_and_fields(
    symbol: str, side: str, quantity: float,
    order_type: str, client_order_id: str, account_id: str,
):
    """ORDER_ATTEMPT output is valid JSON with all required fields."""
    audit = AuditLogger(_config())
    lines = _capture_lines(audit)
    audit.log_order_attempt(symbol, side, quantity, order_type, client_order_id, account_id)

    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["event"] == "ORDER_ATTEMPT"
    assert "timestamp" in data
    assert data["symbol"] == symbol
    assert data["side"] == side
    assert data["quantity"] == quantity
    assert data["order_type"] == order_type
    assert data["client_order_id"] == client_order_id
    assert data["account_id"] == account_id


@settings(max_examples=100)
@given(
    client_order_id=_safe_text,
    success=st.booleans(),
    response=_params_strategy,
)
def test_order_result_json_format_and_fields(
    client_order_id: str, success: bool, response: dict,
):
    """ORDER_RESULT output is valid JSON with client_order_id and success."""
    audit = AuditLogger(_config())
    lines = _capture_lines(audit)
    audit.log_order_result(client_order_id, success, response)

    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["event"] == "ORDER_RESULT"
    assert "timestamp" in data
    assert data["client_order_id"] == client_order_id
    assert data["success"] == success


@settings(max_examples=100)
@given(tool_name=_safe_text, error=_safe_text, params=_params_strategy)
def test_validation_error_json_format_and_fields(tool_name: str, error: str, params: dict):
    """VALIDATION_ERROR output is valid JSON with tool, error, params."""
    audit = AuditLogger(_config())
    lines = _capture_lines(audit)
    audit.log_validation_error(tool_name, error, params)

    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["event"] == "VALIDATION_ERROR"
    assert "timestamp" in data
    assert data["tool"] == tool_name
    assert data["error"] == error
    assert "params" in data


# ---------------------------------------------------------------------------
# Property 10: Audit Log Price Masking
# **Validates: Requirements 15.9**
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    price=st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False),
    stop_price=st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False),
)
def test_price_fields_masked_in_tool_call(price: float, stop_price: float):
    """log_tool_call() must replace price and stop_price with '***'."""
    audit = AuditLogger(_config())
    lines = _capture_lines(audit)
    audit.log_tool_call("place_order", {
        "symbol": "AAPL",
        "price": price,
        "stop_price": stop_price,
        "quantity": 10,
    })

    data = json.loads(lines[0])
    assert data["params"]["price"] == "***"
    assert data["params"]["stop_price"] == "***"
    # Non-sensitive fields preserved
    assert data["params"]["symbol"] == "AAPL"
    assert data["params"]["quantity"] == 10


# ---------------------------------------------------------------------------
# Property 11: Credentials Not Leaked
# **Validates: Requirements 2.3, 15.10**
# ---------------------------------------------------------------------------

# Use a prefix that won't collide with JSON structural text (event names, keys, etc.)
_credential_str = st.text(min_size=8, max_size=40).map(lambda s: f"CRED_{s}_END")


@settings(max_examples=100)
@given(
    app_key=_credential_str,
    app_secret=_credential_str,
    access_token=_credential_str,
)
def test_credentials_never_appear_in_audit_output(
    app_key: str, app_secret: str, access_token: str,
):
    """Actual credential values must never appear in any audit log line."""
    cfg = _config(app_key=app_key, app_secret=app_secret)
    audit = AuditLogger(cfg)
    lines = _capture_lines(audit)

    # Emit all four event types, injecting credential values into params
    params_with_creds = {
        "app_key": app_key,
        "app_secret": app_secret,
        "access_token": access_token,
        "symbol": "TSLA",
    }
    audit.log_tool_call("some_tool", params_with_creds)
    audit.log_order_attempt("AAPL", "BUY", 1, "MARKET", "o1", "a1")
    audit.log_order_result("o1", True, {
        "app_key": app_key,
        "app_secret": app_secret,
        "access_token": access_token,
        "status": "ok",
    })
    audit.log_validation_error("t", "err", params_with_creds)

    full_text = "\n".join(lines)
    assert app_key not in full_text
    assert app_secret not in full_text
    assert access_token not in full_text
