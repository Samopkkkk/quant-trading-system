"""Unit tests for the AuditLogger class."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from unittest.mock import patch

import pytest

from webull_openapi_mcp.audit import AuditLogger
from webull_openapi_mcp.config import ServerConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**overrides) -> ServerConfig:
    defaults = dict(app_key="test_key", app_secret="test_secret")
    defaults.update(overrides)
    return ServerConfig(**defaults)


def _capture_log_lines(audit: AuditLogger) -> list[str]:
    """Return a list that collects every line emitted by *audit*."""
    lines: list[str] = []

    class _Capture(logging.Handler):  # NOSONAR - test-only log capture handler
        def emit(self, record: logging.LogRecord) -> None:
            lines.append(record.getMessage())

    audit._logger.addHandler(_Capture())
    return lines


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestInit:
    def test_stderr_handler_always_present(self):
        audit = AuditLogger(_make_config())
        handler_types = [type(h) for h in audit._logger.handlers]
        assert logging.StreamHandler in handler_types

    def test_no_file_handler_when_not_configured(self):
        audit = AuditLogger(_make_config())
        from logging.handlers import RotatingFileHandler
        handler_types = [type(h) for h in audit._logger.handlers]
        assert RotatingFileHandler not in handler_types

    def test_file_handler_when_configured(self):
        from logging.handlers import RotatingFileHandler
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
            path = f.name
        try:
            audit = AuditLogger(_make_config(audit_log_file=path))
            handler_types = [type(h) for h in audit._logger.handlers]
            assert RotatingFileHandler in handler_types
        finally:
            os.unlink(path)

    def test_file_handler_rotation_settings(self):
        from logging.handlers import RotatingFileHandler
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
            path = f.name
        try:
            audit = AuditLogger(_make_config(audit_log_file=path))
            rfh = [h for h in audit._logger.handlers if isinstance(h, RotatingFileHandler)][0]
            assert rfh.maxBytes == 10 * 1024 * 1024
            assert rfh.backupCount == 5
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# log_tool_call
# ---------------------------------------------------------------------------

class TestLogToolCall:
    def test_basic_event_structure(self):
        audit = AuditLogger(_make_config())
        lines = _capture_log_lines(audit)
        audit.log_tool_call("get_account_list", {"account_id": "123"})

        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["event"] == "TOOL_CALL"
        assert data["tool"] == "get_account_list"
        assert "timestamp" in data
        assert data["params"] == {"account_id": "123"}

    def test_price_sanitized(self):
        audit = AuditLogger(_make_config())
        lines = _capture_log_lines(audit)
        audit.log_tool_call("place_order", {"symbol": "AAPL", "price": 150.5, "quantity": 10})

        data = json.loads(lines[0])
        assert data["params"]["price"] == "***"
        assert data["params"]["symbol"] == "AAPL"
        assert data["params"]["quantity"] == 10

    def test_stop_price_sanitized(self):
        audit = AuditLogger(_make_config())
        lines = _capture_log_lines(audit)
        audit.log_tool_call("place_order", {"stop_price": 140.0})

        data = json.loads(lines[0])
        assert data["params"]["stop_price"] == "***"

    def test_credentials_excluded(self):
        audit = AuditLogger(_make_config())
        lines = _capture_log_lines(audit)
        audit.log_tool_call("some_tool", {
            "app_key": "secret_key",
            "app_secret": "secret_val",
            "access_token": "tok123",
            "symbol": "AAPL",
        })

        data = json.loads(lines[0])
        assert "app_key" not in data["params"]
        assert "app_secret" not in data["params"]
        assert "access_token" not in data["params"]
        assert data["params"]["symbol"] == "AAPL"

    def test_original_params_not_mutated(self):
        audit = AuditLogger(_make_config())
        lines = _capture_log_lines(audit)
        original = {"price": 100.0, "symbol": "TSLA"}
        audit.log_tool_call("preview_order", original)

        assert original["price"] == 100.0  # not mutated


# ---------------------------------------------------------------------------
# log_order_attempt
# ---------------------------------------------------------------------------

class TestLogOrderAttempt:
    def test_event_structure(self):
        audit = AuditLogger(_make_config())
        lines = _capture_log_lines(audit)
        audit.log_order_attempt(
            symbol="AAPL", side="BUY", quantity=10,
            order_type="LIMIT", client_order_id="ord-1", account_id="acc-1",
        )

        data = json.loads(lines[0])
        assert data["event"] == "ORDER_ATTEMPT"
        assert data["symbol"] == "AAPL"
        assert data["side"] == "BUY"
        assert data["quantity"] == 10
        assert data["order_type"] == "LIMIT"
        assert data["client_order_id"] == "ord-1"
        assert data["account_id"] == "acc-1"
        assert "timestamp" in data


# ---------------------------------------------------------------------------
# log_order_result
# ---------------------------------------------------------------------------

class TestLogOrderResult:
    def test_event_structure(self):
        audit = AuditLogger(_make_config())
        lines = _capture_log_lines(audit)
        audit.log_order_result("ord-1", True, {"order_id": "12345"})

        data = json.loads(lines[0])
        assert data["event"] == "ORDER_RESULT"
        assert data["client_order_id"] == "ord-1"
        assert data["success"] is True
        assert data["response"] == {"order_id": "12345"}
        assert "timestamp" in data

    def test_credentials_stripped_from_response(self):
        audit = AuditLogger(_make_config())
        lines = _capture_log_lines(audit)
        audit.log_order_result("ord-1", False, {
            "app_key": "k", "app_secret": "s", "access_token": "t",
            "status": "FAILED",
        })

        data = json.loads(lines[0])
        assert "app_key" not in data["response"]
        assert "app_secret" not in data["response"]
        assert "access_token" not in data["response"]
        assert data["response"]["status"] == "FAILED"

    def test_nested_credentials_stripped(self):
        audit = AuditLogger(_make_config())
        lines = _capture_log_lines(audit)
        audit.log_order_result("ord-1", True, {
            "data": {"app_secret": "hidden", "value": 42},
            "items": [{"access_token": "tok", "id": 1}],
        })

        data = json.loads(lines[0])
        assert "app_secret" not in data["response"]["data"]
        assert data["response"]["data"]["value"] == 42
        assert "access_token" not in data["response"]["items"][0]
        assert data["response"]["items"][0]["id"] == 1


# ---------------------------------------------------------------------------
# log_validation_error
# ---------------------------------------------------------------------------

class TestLogValidationError:
    def test_event_structure(self):
        audit = AuditLogger(_make_config())
        lines = _capture_log_lines(audit)
        audit.log_validation_error("place_order", "quantity must be positive", {"quantity": -1})

        data = json.loads(lines[0])
        assert data["event"] == "VALIDATION_ERROR"
        assert data["tool"] == "place_order"
        assert data["error"] == "quantity must be positive"
        assert data["params"] == {"quantity": -1}
        assert "timestamp" in data

    def test_credentials_excluded_from_params(self):
        audit = AuditLogger(_make_config())
        lines = _capture_log_lines(audit)
        audit.log_validation_error("place_order", "bad", {
            "app_key": "k", "symbol": "AAPL",
        })

        data = json.loads(lines[0])
        assert "app_key" not in data["params"]
        assert data["params"]["symbol"] == "AAPL"

    def test_price_sanitized_in_validation_error(self):
        audit = AuditLogger(_make_config())
        lines = _capture_log_lines(audit)
        audit.log_validation_error("place_order", "bad price", {
            "price": 999.99, "stop_price": 888.88,
        })

        data = json.loads(lines[0])
        assert data["params"]["price"] == "***"
        assert data["params"]["stop_price"] == "***"


# ---------------------------------------------------------------------------
# JSON format & timestamp
# ---------------------------------------------------------------------------

class TestJsonFormat:
    def test_each_line_is_valid_json(self):
        audit = AuditLogger(_make_config())
        lines = _capture_log_lines(audit)

        audit.log_tool_call("t1", {})
        audit.log_order_attempt("S", "BUY", 1, "MARKET", "o1", "a1")
        audit.log_order_result("o1", True, {})
        audit.log_validation_error("t1", "err", {})

        assert len(lines) == 4
        for line in lines:
            data = json.loads(line)  # must not raise
            assert "event" in data
            assert "timestamp" in data

    def test_timestamp_is_utc_iso(self):
        audit = AuditLogger(_make_config())
        lines = _capture_log_lines(audit)
        audit.log_tool_call("t", {})

        data = json.loads(lines[0])
        ts = data["timestamp"]
        # Should end with +00:00 (UTC)
        assert "+00:00" in ts or ts.endswith("Z")


# ---------------------------------------------------------------------------
# stderr isolation
# ---------------------------------------------------------------------------

class TestStderrIsolation:
    def test_output_goes_to_stderr_not_stdout(self, capsys):
        audit = AuditLogger(_make_config())
        audit.log_tool_call("test_tool", {"x": 1})

        captured = capsys.readouterr()
        assert captured.out == ""
        # stderr should have content (capsys captures it)
        assert "TOOL_CALL" in captured.err


# ---------------------------------------------------------------------------
# Credential values never appear in raw log text
# ---------------------------------------------------------------------------

class TestCredentialLeakage:
    def test_config_credentials_not_in_log_text(self):
        cfg = _make_config(app_key="MY_SECRET_KEY_123", app_secret="MY_SECRET_VAL_456")
        audit = AuditLogger(cfg)
        lines = _capture_log_lines(audit)

        audit.log_tool_call("t", {"data": "hello"})
        audit.log_order_attempt("AAPL", "BUY", 1, "MARKET", "o1", "a1")
        audit.log_order_result("o1", True, {"result": "ok"})
        audit.log_validation_error("t", "err", {"x": 1})

        full_text = "\n".join(lines)
        assert "MY_SECRET_KEY_123" not in full_text
        assert "MY_SECRET_VAL_456" not in full_text
