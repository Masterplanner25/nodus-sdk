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


def _published_nodus_http():
    """The real nodus-http, or a reason this cannot be checked here.

    A development checkout resolves `nodus_http` to the incubator **scaffold**
    at `Coding Language/packages/nodus-http/`, which exports
    `NodusHttpClient` and nothing the bridge uses. The bridge targets the
    published package's `HttpClient`, so with the scaffold on the path there is
    nothing to test -- and saying so is the point: `assert client is not None`
    used to pass here against the scaffold while
    `pip install nodus-sdk[http]` raised `ImportError`.
    """
    try:
        import nodus_http
    except ImportError:
        pytest.skip("nodus-http not installed")
    if not hasattr(nodus_http, "HttpClient"):
        pytest.skip(
            f"nodus_http resolves to {nodus_http.__file__}, which has no "
            "HttpClient -- the packages/ scaffold is shadowing the published "
            "package, so this cannot be checked in this environment"
        )
    return nodus_http


def test_http_bridge_client_is_the_published_client():
    """Not `is not None`. That passed for the life of the package against a
    scaffold whose client shares no API with the real one."""
    nodus_http = _published_nodus_http()
    from nodus_sdk.bridges.http import HttpBridge

    client = HttpBridge().client()
    assert isinstance(client, nodus_http.HttpClient)
    # The production API, which the scaffold's client does not have.
    for verb in ("get", "post", "put", "delete"):
        assert hasattr(client, verb), f"the client has no {verb}()"


def test_http_bridge_passes_every_option_it_accepts():
    """`timeout` and `retry_config` were accepted, stored, and dropped.

    `HttpBridge(timeout=5)` built a client on the 30-second default. Checked by
    reading what reached the constructor rather than the client's attributes,
    since those are nodus-http's business and may be named anything.
    """
    nodus_http = _published_nodus_http()
    from nodus_sdk.bridges import http as http_mod

    seen = {}

    class _Spy:
        def __init__(self, **kwargs):
            seen.update(kwargs)

    with patch.object(nodus_http, "HttpClient", _Spy):
        sentinel_cb, sentinel_retry = object(), object()
        http_mod.HttpBridge(
            base_url="https://example.test",
            timeout=5.0,
            circuit_breaker=sentinel_cb,
            retry_config=sentinel_retry,
        ).client()

    assert seen.get("base_url") == "https://example.test"
    assert seen.get("timeout") == 5.0, f"timeout was dropped: {seen}"
    assert seen.get("circuit_breaker") is sentinel_cb
    assert seen.get("retry") is sentinel_retry, f"retry_config was dropped: {seen}"


def test_http_bridge_says_mismatch_not_missing_when_the_symbol_is_gone(monkeypatch):
    """The failure that shipped: a package that *is* installed, reported absent.

    `client()` raised `ImportError: cannot import name 'NodusHttpClient'`
    against the published package, and the bridge's own not-installed message
    says `pip install nodus-sdk[http]` -- advice that cannot help someone who
    already has it. A missing symbol behind an installed package now says
    "version mismatch" and names the package.
    """
    try:
        import nodus_http
    except ImportError:
        pytest.skip("nodus-http not installed")
    from nodus_sdk.bridges.http import HttpBridge

    # `monkeypatch.delattr` restores on teardown; raising=False so this works
    # in an environment where the scaffold is shadowing and it is already gone.
    monkeypatch.delattr(nodus_http, "HttpClient", raising=False)
    with pytest.raises(AttributeError, match="version mismatch"):
        HttpBridge().client()


def test_http_bridge_default_timeout():
    from nodus_sdk.bridges.http import HttpBridge
    b = HttpBridge()
    assert b._timeout == 30.0
