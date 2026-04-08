"""Tests for config.py — ServerConfig, load_config, validate_config."""

from __future__ import annotations

import os
import tempfile
import textwrap

import pytest

from webull_openapi_mcp.config import (
    ServerConfig,
    _parse_float,
    _parse_whitelist,
    load_config,
    validate_config,
)
from webull_openapi_mcp.errors import ConfigError

_TEST_AUDIT_LOG = os.path.join(tempfile.gettempdir(), "webull_test_audit.log")
_TEST_TOKEN_DIR = os.path.join(tempfile.gettempdir(), "webull_test_tokens")


# ---------------------------------------------------------------------------
# Helper: temporarily set env vars and clean up afterwards
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Remove all WEBULL_* env vars before each test to avoid leakage."""
    for key in list(os.environ):
        if key.startswith("WEBULL_"):
            monkeypatch.delenv(key, raising=False)


# ---------------------------------------------------------------------------
# ServerConfig dataclass
# ---------------------------------------------------------------------------

class TestServerConfig:
    def test_not_frozen(self):
        """ServerConfig is no longer frozen due to property methods."""
        cfg = ServerConfig(app_key="k", app_secret="s")
        # Can modify (not frozen anymore)
        cfg.app_key = "other"
        assert cfg.app_key == "other"

    def test_defaults(self):
        cfg = ServerConfig(app_key="k", app_secret="s")
        assert cfg.region_id == "us"
        assert cfg.environment == "uat"
        assert cfg.max_order_notional_usd == 10_000.0
        assert cfg.max_order_notional_hkd == 80_000.0
        assert cfg.max_order_notional_cnh == 70_000.0
        # Legacy property
        assert cfg.max_order_notional == 10_000.0
        assert cfg.max_order_quantity == 1_000.0
        assert cfg.symbol_whitelist is None
        assert cfg.audit_log_file is None
        assert cfg.token_dir is None

    def test_custom_values(self):
        cfg = ServerConfig(
            app_key="k",
            app_secret="s",
            region_id="hk",
            environment="uat",
            max_order_notional_usd=5_000.0,
            max_order_notional_hkd=40_000.0,
            max_order_notional_cnh=35_000.0,
            max_order_quantity=500.0,
            symbol_whitelist=["AAPL", "TSLA"],
            audit_log_file=_TEST_AUDIT_LOG,
            token_dir=_TEST_TOKEN_DIR,
        )
        assert cfg.region_id == "hk"
        assert cfg.environment == "uat"
        assert cfg.max_order_notional_usd == 5_000.0
        assert cfg.max_order_notional_hkd == 40_000.0
        assert cfg.max_order_notional_cnh == 35_000.0
        assert cfg.symbol_whitelist == ["AAPL", "TSLA"]
        assert cfg.token_dir == _TEST_TOKEN_DIR
    
    def test_get_max_notional_for_market(self):
        cfg = ServerConfig(
            app_key="k",
            app_secret="s",
            max_order_notional_usd=10_000.0,
            max_order_notional_hkd=80_000.0,
            max_order_notional_cnh=70_000.0,
        )
        assert cfg.get_max_notional_for_market("US") == (10_000.0, "USD")
        assert cfg.get_max_notional_for_market("HK") == (80_000.0, "HKD")
        assert cfg.get_max_notional_for_market("CN") == (70_000.0, "CNH")
        assert cfg.get_max_notional_for_market(None) == (10_000.0, "USD")


# ---------------------------------------------------------------------------
# _parse_whitelist
# ---------------------------------------------------------------------------

class TestParseWhitelist:
    def test_none(self):
        assert _parse_whitelist(None) is None

    def test_empty_string(self):
        assert _parse_whitelist("") is None

    def test_whitespace_only(self):
        assert _parse_whitelist("   ") is None

    def test_single_symbol(self):
        assert _parse_whitelist("AAPL") == ["AAPL"]

    def test_multiple_symbols(self):
        assert _parse_whitelist("AAPL, TSLA , GOOG") == ["AAPL", "TSLA", "GOOG"]

    def test_trailing_comma(self):
        assert _parse_whitelist("AAPL,TSLA,") == ["AAPL", "TSLA"]

    def test_only_commas(self):
        assert _parse_whitelist(",,,") is None


# ---------------------------------------------------------------------------
# _parse_float
# ---------------------------------------------------------------------------

class TestParseFloat:
    def test_none_returns_default(self):
        assert _parse_float(None, 42.0) == 42.0

    def test_valid_string(self):
        assert _parse_float("123.45", 0.0) == 123.45

    def test_invalid_string_returns_default(self):
        assert _parse_float("not_a_number", 99.0) == 99.0

    def test_integer_string(self):
        assert _parse_float("500", 0.0) == 500.0


# ---------------------------------------------------------------------------
# load_config — from env vars
# ---------------------------------------------------------------------------

class TestLoadConfigFromEnv:
    def test_minimal_env(self, monkeypatch, tmp_path):
        # Use a non-existent env file to avoid loading .env from current directory
        monkeypatch.setenv("WEBULL_APP_KEY", "my_key")
        monkeypatch.setenv("WEBULL_APP_SECRET", "my_secret")
        # Clear any existing env vars
        monkeypatch.delenv("WEBULL_REGION_ID", raising=False)
        monkeypatch.delenv("WEBULL_ENVIRONMENT", raising=False)
        cfg = load_config(env_file=str(tmp_path / "nonexistent.env"))
        assert cfg.app_key == "my_key"
        assert cfg.app_secret == "my_secret"
        assert cfg.region_id == "us"
        assert cfg.environment == "uat"

    def test_all_env_vars(self, monkeypatch):
        monkeypatch.setenv("WEBULL_APP_KEY", "k")
        monkeypatch.setenv("WEBULL_APP_SECRET", "s")
        monkeypatch.setenv("WEBULL_REGION_ID", "hk")
        monkeypatch.setenv("WEBULL_ENVIRONMENT", "uat")
        monkeypatch.setenv("WEBULL_MAX_ORDER_NOTIONAL_USD", "5000")
        monkeypatch.setenv("WEBULL_MAX_ORDER_NOTIONAL_HKD", "40000")
        monkeypatch.setenv("WEBULL_MAX_ORDER_NOTIONAL_CNH", "35000")
        monkeypatch.setenv("WEBULL_MAX_ORDER_QUANTITY", "200")
        monkeypatch.setenv("WEBULL_SYMBOL_WHITELIST", "AAPL,TSLA")
        monkeypatch.setenv("WEBULL_AUDIT_LOG_FILE", _TEST_AUDIT_LOG)
        monkeypatch.setenv("WEBULL_TOKEN_DIR", _TEST_TOKEN_DIR)
        cfg = load_config()
        assert cfg.app_key == "k"
        assert cfg.app_secret == "s"
        assert cfg.region_id == "hk"
        assert cfg.environment == "uat"
        assert cfg.max_order_notional_usd == 5_000.0
        assert cfg.max_order_notional_hkd == 40_000.0
        assert cfg.max_order_notional_cnh == 35_000.0
        assert cfg.max_order_quantity == 200.0
        assert cfg.symbol_whitelist == ["AAPL", "TSLA"]
        assert cfg.audit_log_file == _TEST_AUDIT_LOG
        assert cfg.token_dir == _TEST_TOKEN_DIR

    def test_missing_key_returns_empty_string(self, monkeypatch, tmp_path):
        # Use a non-existent env file to avoid loading .env from current directory
        monkeypatch.delenv("WEBULL_APP_KEY", raising=False)
        monkeypatch.setenv("WEBULL_APP_SECRET", "s")
        cfg = load_config(env_file=str(tmp_path / "nonexistent.env"))
        assert cfg.app_key == ""

    def test_invalid_numeric_uses_default(self, monkeypatch):
        monkeypatch.setenv("WEBULL_APP_KEY", "k")
        monkeypatch.setenv("WEBULL_APP_SECRET", "s")
        monkeypatch.setenv("WEBULL_MAX_ORDER_NOTIONAL_USD", "abc")
        cfg = load_config()
        assert cfg.max_order_notional_usd == 10_000.0

    def test_empty_whitelist_is_none(self, monkeypatch):
        monkeypatch.setenv("WEBULL_APP_KEY", "k")
        monkeypatch.setenv("WEBULL_APP_SECRET", "s")
        monkeypatch.setenv("WEBULL_SYMBOL_WHITELIST", "")
        cfg = load_config()
        assert cfg.symbol_whitelist is None

    def test_empty_token_dir_is_none(self, monkeypatch):
        monkeypatch.setenv("WEBULL_APP_KEY", "k")
        monkeypatch.setenv("WEBULL_APP_SECRET", "s")
        monkeypatch.setenv("WEBULL_TOKEN_DIR", "")
        cfg = load_config()
        assert cfg.token_dir is None


# ---------------------------------------------------------------------------
# load_config — from .env file
# ---------------------------------------------------------------------------

class TestLoadConfigFromEnvFile:
    def test_loads_from_env_file(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text(
            "WEBULL_APP_KEY=file_key\n"
            "WEBULL_APP_SECRET=file_secret\n"
            "WEBULL_REGION_ID=hk\n"
        )
        cfg = load_config(str(env_file))
        assert cfg.app_key == "file_key"
        assert cfg.app_secret == "file_secret"
        assert cfg.region_id == "hk"

    def test_env_var_overrides_file(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("WEBULL_APP_KEY=file_key\nWEBULL_APP_SECRET=file_secret\n")
        monkeypatch.setenv("WEBULL_APP_KEY", "env_key")
        cfg = load_config(str(env_file))
        # Real env var should take precedence (override=False)
        assert cfg.app_key == "env_key"


# ---------------------------------------------------------------------------
# validate_config
# ---------------------------------------------------------------------------

class TestValidateConfig:
    def test_valid_config_passes(self):
        cfg = ServerConfig(app_key="k", app_secret="s")
        validate_config(cfg)  # should not raise

    def test_empty_app_key_raises(self):
        cfg = ServerConfig(app_key="", app_secret="s")
        with pytest.raises(ConfigError, match="WEBULL_APP_KEY"):
            validate_config(cfg)

    def test_empty_app_secret_raises(self):
        cfg = ServerConfig(app_key="k", app_secret="")
        with pytest.raises(ConfigError, match="WEBULL_APP_SECRET"):
            validate_config(cfg)

    def test_both_empty_raises_for_key_first(self):
        cfg = ServerConfig(app_key="", app_secret="")
        with pytest.raises(ConfigError, match="WEBULL_APP_KEY"):
            validate_config(cfg)
