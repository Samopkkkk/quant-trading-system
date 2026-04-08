# Feature: webull-mcp-server, Property 1: Config Load Round-Trip Consistency
"""Property-based test: config load round-trip consistency.

Validates: Requirements 2.1
"""

from __future__ import annotations

import os

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from webull_openapi_mcp.config import load_config


# Strategy: non-empty printable strings without newlines (env vars can't
# reliably contain newlines across platforms).
_env_str = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S", "Z"),
        blacklist_characters="\n\r\x00",
    ),
    min_size=1,
)


@pytest.fixture(autouse=True)
def _clean_webull_env(monkeypatch):
    """Remove all WEBULL_* env vars before each test to avoid leakage."""
    for key in list(os.environ):
        if key.startswith("WEBULL_"):
            monkeypatch.delenv(key, raising=False)


@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    app_key=_env_str,
    app_secret=_env_str,
    region_id=_env_str,
)
def test_load_config_round_trip(app_key: str, app_secret: str, region_id: str, monkeypatch):
    """For any non-empty app_key/app_secret/region_id strings set as env vars,
    load_config() must produce a ServerConfig whose fields match exactly."""
    monkeypatch.setenv("WEBULL_APP_KEY", app_key)
    monkeypatch.setenv("WEBULL_APP_SECRET", app_secret)
    monkeypatch.setenv("WEBULL_REGION_ID", region_id)

    config = load_config()

    assert config.app_key == app_key
    assert config.app_secret == app_secret
    assert config.region_id == region_id


# Feature: webull-mcp-server, Property 2: Missing Credentials Must Be Rejected
"""Property-based test: missing credentials must be rejected.

Validates: Requirements 2.2
"""

from webull_openapi_mcp.config import ServerConfig, validate_config
from webull_openapi_mcp.errors import ConfigError


# Strategy: either empty string or a non-empty text value for each credential.
_maybe_empty = st.one_of(st.just(""), st.text(min_size=1))


@settings(max_examples=100)
@given(
    app_key=_maybe_empty,
    app_secret=_maybe_empty,
)
def test_validate_config_rejects_missing_credentials(app_key: str, app_secret: str):
    """When at least one of app_key/app_secret is empty, validate_config()
    must raise ConfigError."""
    # Only test combinations where at least one credential is missing.
    from hypothesis import assume

    assume(app_key == "" or app_secret == "")

    config = ServerConfig(app_key=app_key, app_secret=app_secret)

    with pytest.raises(ConfigError):
        validate_config(config)
