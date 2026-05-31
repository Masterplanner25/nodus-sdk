"""Tests for bridges/http.py — HttpBridge."""

from __future__ import annotations

from unittest.mock import patch

import pytest


def test_http_bridge_available_false_when_not_installed():
    from nodus_sdk.bridges import http as http_mod
    with patch.object(http_mod, "_AVAILABLE", False):
        from nodus_sdk.bridges.http import HttpBridge
        b = HttpBridge()
        assert b.available() is False


def test_http_bridge_available_true_when_installed():
    try:
        import nodus_http  # noqa: F401
    except ImportError:
        pytest.skip("nodus-http not installed")
    from nodus_sdk.bridges.http import HttpBridge
    b = HttpBridge()
    assert b.available() is True


def test_http_bridge_client_raises_when_not_installed():
    from nodus_sdk.bridges import http as http_mod
    with patch.object(http_mod, "_AVAILABLE", False):
        from nodus_sdk.bridges.http import HttpBridge
        b = HttpBridge()
        with pytest.raises(ImportError, match="nodus-http"):
            b.client()


def test_http_bridge_client_when_available():
    try:
        import nodus_http  # noqa: F401
    except ImportError:
        pytest.skip("nodus-http not installed")
    from nodus_sdk.bridges.http import HttpBridge
    b = HttpBridge()
    client = b.client()
    assert client is not None


def test_http_bridge_default_timeout():
    from nodus_sdk.bridges.http import HttpBridge
    b = HttpBridge()
    assert b._timeout == 30.0
