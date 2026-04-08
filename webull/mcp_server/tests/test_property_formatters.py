# Feature: webull-mcp-server, Property 15: Disclaimer Prefix
"""Property-based test verifying that prepend_disclaimer() always prefixes
content with the DISCLAIMER text.

**Validates: Requirements 18.1**
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from webull_openapi_mcp.formatters import DISCLAIMER, prepend_disclaimer


@settings(max_examples=100)
@given(content=st.text())
def test_prepend_disclaimer_always_starts_with_disclaimer(content: str) -> None:
    """For any content string, prepend_disclaimer(content) must start with DISCLAIMER."""
    result = prepend_disclaimer(content)
    assert result.startswith(DISCLAIMER), (
        f"Expected result to start with DISCLAIMER, but got: {result!r:.200}"
    )


@settings(max_examples=100)
@given(content=st.text())
def test_prepend_disclaimer_preserves_content_after_disclaimer(content: str) -> None:
    """For any content string, the original content must appear immediately after DISCLAIMER."""
    result = prepend_disclaimer(content)
    assert result == DISCLAIMER + content
