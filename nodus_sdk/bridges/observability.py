"""Observability bridge — thin wrapper over nodus-observability bootstrap."""

from __future__ import annotations

import importlib.util

_AVAILABLE = importlib.util.find_spec("nodus_observability") is not None


def available() -> bool:
    return _AVAILABLE


def init_observability(
    service_name: str,
    *,
    otel: bool = False,
    prometheus: bool = False,
    configure_logging: bool = True,
) -> None:
    """Bootstrap observability for the given service.

    Calls nodus-observability's init_otel() and/or create_registry() depending
    on the flags. Safe to call multiple times (subsequent calls are no-ops at
    the nodus-observability layer).

    Requires ``nodus-sdk[observability]``.
    """
    if not _AVAILABLE:
        return

    if configure_logging:
        try:
            from nodus_observability import configure_logging as _conf_logging
            _conf_logging()
        except (ImportError, TypeError):
            pass

    if otel:
        try:
            from nodus_observability import init_otel
            init_otel(service_name)
        except (ImportError, TypeError):
            pass

    if prometheus:
        try:
            from nodus_observability import create_registry
            create_registry()
        except (ImportError, TypeError):
            pass
