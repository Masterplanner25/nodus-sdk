"""HttpBridge — thin bridge over nodus-http."""

from __future__ import annotations

import importlib.util
from typing import Any

from nodus_sdk.runtime import _require

_AVAILABLE = importlib.util.find_spec("nodus_http") is not None


class HttpBridge:
    """Thin bridge wrapping nodus-http's HttpClient with optional circuit-breaker.

    Requires ``nodus-sdk[http]`` (``nodus-http``).
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 30.0,
        circuit_breaker: Any = None,
        retry_config: Any = None,
    ) -> None:
        self._base_url = base_url
        self._timeout = timeout
        self._circuit_breaker = circuit_breaker
        self._retry_config = retry_config

    def available(self) -> bool:
        return _AVAILABLE

    def client(self) -> Any:
        """Return a configured `nodus_http.HttpClient`.

        **`HttpClient`, not `NodusHttpClient`.** This imported the latter, which
        the published nodus-http does not export -- so `pip install
        nodus-sdk[http]` followed by `HttpBridge().client()` raised
        `ImportError` naming a package that *was* installed. `NodusHttpClient`
        belongs to the incubator **scaffold** under `packages/nodus-http/`,
        which a development checkout resolves `nodus_http` to, so the suite
        passed here and the bridge had never run against the real package.

        The two are not interchangeable -- the scaffold's constructor takes
        transports and its one method is `request()`, where the published
        client takes `base_url`/`timeout`/`retry`/`circuit_breaker` and offers
        `get`/`post`/`put`/`delete`. So this targets the published package and
        says so loudly if it finds the other one, rather than returning
        whichever object happens to be importable.

        `timeout` and `retry_config` are passed now. They were accepted,
        stored on the instance, and dropped, so `HttpBridge(timeout=5)` built a
        client with the 30-second default.
        """
        if not _AVAILABLE:
            raise ImportError("nodus-http not installed. pip install nodus-sdk[http]")
        (HttpClient,) = _require("nodus_http", "HttpClient")
        kwargs: dict[str, Any] = {"timeout": self._timeout}
        if self._base_url:
            kwargs["base_url"] = self._base_url
        if self._circuit_breaker is not None:
            kwargs["circuit_breaker"] = self._circuit_breaker
        if self._retry_config is not None:
            kwargs["retry"] = self._retry_config
        return HttpClient(**kwargs)
