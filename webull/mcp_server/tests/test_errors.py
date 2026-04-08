"""Tests for errors.py — exception definitions and SDK error handling."""

import pytest
from webull.core.exception.exceptions import ClientException, ServerException

from webull_openapi_mcp.errors import (
    ConfigError,
    MARKET_DATA_TOOLS,
    MARKET_DATA_SUBSCRIPTION_HINTS,
    ValidationError,
    _get_market_data_hint,
    handle_sdk_exception,
)

_QUANTITY_POSITIVE_MSG = "quantity must be positive"
_NO_ACCESS_MSG = "no access"
_US_QUOTE_URL = "webullapp.com/quote"
_HK_QUOTE_URL = "webullapp.hk/quote"
# ---------------------------------------------------------------------------
# ConfigError
# ---------------------------------------------------------------------------

class TestConfigError:
    def test_is_exception(self):
        assert issubclass(ConfigError, Exception)

    def test_message(self):
        err = ConfigError("missing app_key")
        assert str(err) == "missing app_key"


# ---------------------------------------------------------------------------
# ValidationError
# ---------------------------------------------------------------------------

class TestValidationError:
    def test_message_and_field(self):
        err = ValidationError(_QUANTITY_POSITIVE_MSG, field="quantity")
        assert err.message == _QUANTITY_POSITIVE_MSG
        assert err.field == "quantity"
        assert str(err) == _QUANTITY_POSITIVE_MSG

    def test_field_defaults_to_none(self):
        err = ValidationError("bad value")
        assert err.field is None

    def test_is_exception(self):
        assert issubclass(ValidationError, Exception)


# ---------------------------------------------------------------------------
# handle_sdk_exception — ServerException
# ---------------------------------------------------------------------------

class TestHandleServerException:
    def test_generic_server_error(self):
        exc = ServerException(code="SOME_ERR", msg="something broke", http_status=500)
        result = handle_sdk_exception(exc, "get_account_list")
        assert "500" in result
        assert "SOME_ERR" in result
        assert "something broke" in result

    @pytest.mark.parametrize("tool", list(MARKET_DATA_TOOLS))
    def test_market_data_403_returns_hint(self, tool: str):
        exc = ServerException(code="FORBIDDEN", msg=_NO_ACCESS_MSG, http_status=403)
        result = handle_sdk_exception(exc, tool, region_id="us")
        assert _US_QUOTE_URL in result

    @pytest.mark.parametrize("tool", list(MARKET_DATA_TOOLS))
    def test_market_data_401_returns_hint(self, tool: str):
        exc = ServerException(code="Unauthorized", msg=_NO_ACCESS_MSG, http_status=401)
        result = handle_sdk_exception(exc, tool, region_id="hk")
        assert _HK_QUOTE_URL in result

    def test_non_market_data_403_is_generic(self):
        exc = ServerException(code="FORBIDDEN", msg=_NO_ACCESS_MSG, http_status=403)
        result = handle_sdk_exception(exc, "get_account_list")
        assert "403" in result

    def test_cancel_order_404(self):
        exc = ServerException(code="NOT_FOUND", msg="order missing", http_status=404)
        result = handle_sdk_exception(exc, "cancel_order")
        assert result == "Order not found; it may have been filled or already cancelled"

    def test_cancel_order_403(self):
        exc = ServerException(code="FORBIDDEN", msg="denied", http_status=403)
        result = handle_sdk_exception(exc, "cancel_order")
        assert result == "Permission denied; please check account permissions"

    def test_cancel_order_other_status(self):
        exc = ServerException(code="ERR", msg="bad", http_status=500)
        result = handle_sdk_exception(exc, "cancel_order")
        assert "500" in result


# ---------------------------------------------------------------------------
# handle_sdk_exception — ClientException
# ---------------------------------------------------------------------------

class TestHandleClientException:
    def test_client_exception(self):
        exc = ClientException(code="INVALID_PARAM", msg="symbol is required")
        result = handle_sdk_exception(exc, "place_order")
        assert "Parameter error" in result
        assert "INVALID_PARAM" in result
        assert "symbol is required" in result


# ---------------------------------------------------------------------------
# handle_sdk_exception — generic Exception
# ---------------------------------------------------------------------------

class TestHandleGenericException:
    def test_unknown_exception(self):
        exc = RuntimeError("unexpected")
        result = handle_sdk_exception(exc, "any_tool")
        assert "Internal error" in result
        assert "RuntimeError" in result


# ---------------------------------------------------------------------------
# Market data subscription hints
# ---------------------------------------------------------------------------

class TestMarketDataSubscriptionHints:
    def test_us_hint_contains_url(self):
        hint = _get_market_data_hint("us")
        assert _US_QUOTE_URL in hint
        assert "developer.webull.com" in hint

    def test_hk_hint_contains_url(self):
        hint = _get_market_data_hint("hk")
        assert _HK_QUOTE_URL in hint
        assert "developer.webull.hk" in hint

    def test_fallback_contains_both(self):
        hint = _get_market_data_hint(None)
        assert _US_QUOTE_URL in hint
        assert _HK_QUOTE_URL in hint
