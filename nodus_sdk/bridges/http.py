"""HttpBridge — thin bridge over nodus-http."""

from __future__ import annotations

import importlib.util
from typing import Any

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
        """Return a configured NodusHttpClient."""
        if not _AVAILABLE:
            raise ImportError("nodus-http not installed. pip install nodus-sdk[http]")
        from nodus_http import NodusHttpClient
        kwargs: dict[str, Any] = {}
        if self._base_url:
            kwargs["base_url"] = self._base_url
        if self._circuit_breaker is not None:
            kwargs["circuit_breaker"] = self._circuit_breaker
        return NodusHttpClient(**kwargs)
