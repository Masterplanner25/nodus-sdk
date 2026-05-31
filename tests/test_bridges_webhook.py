"""Tests for bridges/webhook.py — WebhookBridge."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
import respx
import httpx

from nodus_sdk.bridges.webhook import WebhookBridge, _sign_payload
from nodus_sdk import NodusSDKRuntime


# ---------------------------------------------------------------------------
# _sign_payload helper
# ---------------------------------------------------------------------------

def test_sign_payload_produces_sha256():
    sig = _sign_payload("mysecret", b'{"key":"value"}')
    assert sig.startswith("sha256=")
    expected = "sha256=" + hmac.new(b"mysecret", b'{"key":"value"}', hashlib.sha256).hexdigest()
    assert sig == expected


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def test_webhook_bridge_creates():
    b = WebhookBridge()
    assert b is not None


def test_webhook_bridge_stores_secret():
    b = WebhookBridge(secret="abc123")
    assert b._secret == "abc123"


def test_webhook_bridge_raises_without_httpx():
    from nodus_sdk.bridges import webhook as wh_mod
    from unittest.mock import patch
    with patch.object(wh_mod, "_HTTPX_AVAILABLE", False):
        with pytest.raises(ImportError, match="httpx"):
            WebhookBridge()


# ---------------------------------------------------------------------------
# send() — mocked with respx
# ---------------------------------------------------------------------------

@respx.mock
def test_send_posts_to_url():
    respx.post("https://example.com/hook").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    b = WebhookBridge()
    result = b.send("https://example.com/hook", {"event": "test"})
    assert result["status"] == "ok"
    assert result["status_code"] == 200


@respx.mock
def test_send_returns_error_on_4xx():
    respx.post("https://example.com/hook").mock(
        return_value=httpx.Response(404, json={"error": "not found"})
    )
    b = WebhookBridge()
    result = b.send("https://example.com/hook", {})
    assert result["status"] == "error"
    assert result["status_code"] == 404


@respx.mock
def test_send_includes_signature_header_when_secret():
    route = respx.post("https://example.com/hook").mock(
        return_value=httpx.Response(200, json={})
    )
    b = WebhookBridge(secret="testsecret")
    b.send("https://example.com/hook", {"x": "y"})
    req = route.calls[0].request
    assert "X-Nodus-Signature" in req.headers
    assert req.headers["X-Nodus-Signature"].startswith("sha256=")


@respx.mock
def test_send_includes_event_type_header():
    route = respx.post("https://example.com/hook").mock(
        return_value=httpx.Response(200, json={})
    )
    b = WebhookBridge()
    b.send("https://example.com/hook", {}, event_type="order.placed")
    req = route.calls[0].request
    assert req.headers["X-Nodus-Event"] == "order.placed"


@respx.mock
def test_send_returns_error_on_network_failure():
    respx.post("https://unreachable.invalid/").mock(side_effect=httpx.ConnectError("conn refused"))
    b = WebhookBridge()
    result = b.send("https://unreachable.invalid/", {})
    assert result["status"] == "error"


# ---------------------------------------------------------------------------
# register_host_functions
# ---------------------------------------------------------------------------

@respx.mock
def test_webhook_send_callable_from_nd():
    respx.post("https://example.com/wh").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    rt = NodusSDKRuntime(timeout_ms=None)
    b = WebhookBridge()
    b.register_host_functions(rt)
    result = rt.run_source('let r = webhook_send("https://example.com/wh", {}, "test.event")\nprint(r["status"])')
    assert result.get("ok") is True
    assert "ok" in result.get("stdout", "")
