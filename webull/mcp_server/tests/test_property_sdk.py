# Feature: webull-mcp-server, Property 3: Environment-Driven Endpoint Selection
"""Property test: environment-driven endpoint selection.

For any valid region_id, when environment is "uat", WebullSDKClient.initialize()
must call api_client.add_endpoint(region_id, uat_api_endpoint); when environment
is "prod", add_endpoint must NOT be called.

Validates: Requirements 1.4, 1.5
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from webull_openapi_mcp.config import ServerConfig
from webull_openapi_mcp.sdk_client import UAT_ENDPOINTS, WebullSDKClient

_ENVIRONMENTS = ["uat", "prod"]
_REGION_IDS = ["us", "hk"]


@pytest.mark.parametrize(
    "environment,region_id",
    [(env, rid) for env in _ENVIRONMENTS for rid in _REGION_IDS],
    ids=[f"{env}-{rid}" for env in _ENVIRONMENTS for rid in _REGION_IDS],
)
@patch("webull_openapi_mcp.sdk_client.DataClient")
@patch("webull_openapi_mcp.sdk_client.TradeClient")
@patch("webull_openapi_mcp.sdk_client.ApiClient")
def test_endpoint_selection_by_environment(
    MockApiClient,
    MockTradeClient,
    MockDataClient,
    environment: str,
    region_id: str,
):
    """UAT must inject all endpoint types via add_endpoint; prod must not."""
    cfg = ServerConfig(
        app_key="test_key",
        app_secret="test_secret",
        region_id=region_id,
        environment=environment,
    )
    client = WebullSDKClient(cfg)
    client.initialize()

    api = MockApiClient.return_value

    if environment == "uat":
        # Should register all three endpoint types
        assert api.add_endpoint.call_count == 3
    else:
        api.add_endpoint.assert_not_called()
