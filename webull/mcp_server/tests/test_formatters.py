"""Unit tests for webull_openapi_mcp.formatters."""

from __future__ import annotations

import pytest

from webull_openapi_mcp.formatters import (
    DISCLAIMER,
    format_account_balance,
    format_account_list,
    format_crypto_bars,
    format_crypto_snapshot,
    format_instruments,
    format_open_orders,
    format_order_detail,
    format_order_history,
    format_place_option_order_result,
    format_place_order_result,
    format_positions,
    format_preview_option_order,
    format_preview_order,
    format_stock_bars,
    format_stock_quotes,
    format_stock_snapshot,
    format_stock_tick,
    prepend_disclaimer,
)


# ---------------------------------------------------------------------------
# prepend_disclaimer
# ---------------------------------------------------------------------------

class TestPrependDisclaimer:
    def test_prepends_disclaimer_to_content(self):
        result = prepend_disclaimer("hello")
        assert result.startswith(DISCLAIMER)
        assert result == DISCLAIMER + "hello"

    def test_empty_content(self):
        result = prepend_disclaimer("")
        assert result == DISCLAIMER

    def test_disclaimer_contains_bilingual_text(self):
        assert "Disclaimer" in DISCLAIMER
        assert "investment advice" in DISCLAIMER


# ---------------------------------------------------------------------------
# Empty / None data handling
# ---------------------------------------------------------------------------

_NO_DATA = "No data available."

@pytest.mark.parametrize("fn", [
    format_account_list,
    format_account_balance,
    format_positions,
    format_stock_snapshot,
    format_stock_quotes,
    format_stock_bars,
    format_stock_tick,
    format_crypto_snapshot,
    format_crypto_bars,
    format_order_history,
    format_open_orders,
    format_order_detail,
    format_instruments,
    format_preview_order,
    format_preview_option_order,
    format_place_order_result,
    format_place_option_order_result,
])
def test_returns_no_data_for_none(fn):
    assert fn(None) == _NO_DATA


@pytest.mark.parametrize("fn,empty", [
    (format_account_list, []),
    (format_positions, []),
    (format_stock_snapshot, []),
    (format_stock_quotes, []),
    (format_stock_bars, []),
    (format_stock_tick, []),
    (format_crypto_snapshot, []),
    (format_crypto_bars, []),
    (format_order_history, []),
    (format_open_orders, []),
    (format_instruments, []),
])
def test_returns_no_data_for_empty_list(fn, empty):
    assert fn(empty) == _NO_DATA


@pytest.mark.parametrize("fn,empty", [
    (format_account_balance, {}),
    (format_order_detail, {}),
    (format_preview_order, {}),
    (format_preview_option_order, {}),
    (format_place_order_result, {}),
    (format_place_option_order_result, {}),
])
def test_dict_formatters_handle_empty_dict(fn, empty):
    # Empty dicts are falsy via `not data`, so they return _NO_DATA
    result = fn(empty)
    assert result == _NO_DATA


# ---------------------------------------------------------------------------
# Specific formatter output tests
# ---------------------------------------------------------------------------

class TestFormatAccountList:
    def test_formats_single_account(self):
        data = [{"account_id": "123", "account_number": "A001",
                 "account_type": "CASH", "account_class": "1",
                 "account_label": "Main"}]
        result = format_account_list(data)
        assert "123" in result
        assert "A001" in result
        assert "CASH" in result
        assert "Main" in result

    def test_formats_multiple_accounts(self):
        data = [
            {"account_id": "1", "account_number": "N1"},
            {"account_id": "2", "account_number": "N2"},
        ]
        result = format_account_list(data)
        assert "1." in result
        assert "2." in result


class TestFormatAccountBalance:
    def test_formats_balance_fields(self):
        data = {
            "total_asset_currency": "USD",
            "total_cash_balance": "10000.00",
            "total_market_value": "40000.00",
            "total_unrealized_profit_loss": "500.00",
            "total_net_liquidation_value": "50000.00",
            "account_currency_assets": [
                {
                    "currency": "USD",
                    "cash_balance": "10000.00",
                    "buying_power": "25000.00",
                    "market_value": "40000.00",
                    "unrealized_profit_loss": "500.00",
                }
            ],
        }
        result = format_account_balance(data)
        assert "50000.00" in result
        assert "25000.00" in result
        assert "Buying Power" in result


class TestFormatPositions:
    def test_formats_position(self):
        data = [{"symbol": "AAPL", "quantity": "10", "instrument_type": "STOCK",
                 "cost_price": "150.00", "last_price": "155.00",
                 "currency": "USD", "unrealized_profit_loss": "50.00"}]
        result = format_positions(data)
        assert "AAPL" in result
        assert "150.00" in result
        assert "50.00" in result


class TestFormatStockSnapshot:
    def test_formats_snapshot(self):
        data = [{"symbol": "TSLA", "price": "250.00",
                 "pre_close": "245.00",
                 "change": "+5.00", "change_ratio": "2.04",
                 "volume": "1000000", "bid": "249.90",
                 "bid_size": "100", "ask": "250.10", "ask_size": "200",
                 "open": "246.00", "high": "251.00", "low": "244.50",
                 "close": "250.00"}]
        result = format_stock_snapshot(data)
        assert "TSLA" in result
        assert "250.00" in result
        assert "1000000" in result


class TestFormatStockBars:
    def test_formats_bars(self):
        data = [{"time": "2025-01-15 10:00", "open": "100",
                 "high": "105", "low": "99", "close": "103",
                 "volume": "50000"}]
        result = format_stock_bars(data)
        assert "OHLCV" in result
        assert "100" in result
        assert "105" in result


class TestFormatOrderHistory:
    def test_formats_orders(self):
        data = [{"client_order_id": "ORD1", "combo_type": "NORMAL",
                 "orders": [{"client_order_id": "ORD1", "symbol": "AAPL",
                             "side": "BUY", "order_type": "LIMIT",
                             "quantity": "10", "filled_quantity": "10",
                             "limit_price": "150", "avg_filled_price": "149.50",
                             "status": "FILLED", "time_in_force": "DAY",
                             "create_time": "2025-01-15"}]}]
        result = format_order_history(data)
        assert "ORD1" in result
        assert "FILLED" in result


class TestFormatOrderDetail:
    def test_formats_detail(self):
        data = {"client_order_id": "ORD2", "combo_type": "NORMAL",
                "orders": [{"client_order_id": "ORD2", "symbol": "GOOG",
                            "side": "SELL", "order_type": "MARKET",
                            "total_quantity": "5", "status": "COMPLETED"}]}
        result = format_order_detail(data)
        assert "ORD2" in result
        assert "GOOG" in result
        assert "SELL" in result


class TestFormatInstruments:
    def test_formats_instruments(self):
        data = [{"symbol": "AAPL", "name": "Apple Inc.",
                 "instrument_type": "STOCK", "exchange": "NASDAQ"}]
        result = format_instruments(data)
        assert "AAPL" in result
        assert "Apple Inc." in result
        assert "NASDAQ" in result


class TestFormatPreviewOrder:
    def test_formats_preview(self):
        data = {"symbol": "AAPL", "side": "BUY", "quantity": "10",
                "order_type": "LIMIT", "price": "150.00",
                "total_cost": "1500.00", "commission": "0.00",
                "fees": "0.01"}
        result = format_preview_order(data)
        assert "Preview" in result
        assert "1500.00" in result


class TestFormatPreviewOptionOrder:
    def test_formats_option_preview_with_legs(self):
        data = {"strategy": "VERTICAL", "order_type": "LIMIT",
                "total_cost": "200.00", "commission": "1.30",
                "fees": "0.10",
                "legs": [
                    {"symbol": "AAPL", "side": "BUY", "quantity": "1",
                     "option_type": "CALL", "strike_price": "150",
                     "option_expire_date": "2025-02-21"},
                    {"symbol": "AAPL", "side": "SELL", "quantity": "1",
                     "option_type": "CALL", "strike_price": "160",
                     "option_expire_date": "2025-02-21"},
                ]}
        result = format_preview_option_order(data)
        assert "VERTICAL" in result
        assert "Legs:" in result
        assert "150" in result
        assert "160" in result

    def test_formats_option_preview_no_legs(self):
        data = {"strategy": "SINGLE", "order_type": "LIMIT"}
        result = format_preview_option_order(data)
        assert "SINGLE" in result
        assert "Legs:" not in result


class TestFormatPlaceOrderResult:
    def test_formats_result(self):
        data = {"client_order_id": "ORD3", "status": "SUBMITTED"}
        result = format_place_order_result(data)
        assert "ORD3" in result
        assert "SUBMITTED" in result


class TestFormatPlaceOptionOrderResult:
    def test_formats_result(self):
        data = {"client_order_id": "OPT1", "status": "SUBMITTED"}
        result = format_place_option_order_result(data)
        assert "OPT1" in result
        assert "Option" in result
