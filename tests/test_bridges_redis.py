"""Tests for bridges/redis.py — RedisBridge."""

from __future__ import annotations

from unittest.mock import patch

import pytest


def test_redis_bridge_available_false_when_not_installed():
    from nodus_sdk.bridges import redis as redis_mod
    with patch.object(redis_mod, "_QUEUE_AVAILABLE", False), \
         patch.object(redis_mod, "_EVENTS_AVAILABLE", False):
        from nodus_sdk.bridges.redis import RedisBridge
        b = RedisBridge("redis://localhost:6379")
        assert b.available() is False


def test_redis_bridge_redis_url_stored():
    from nodus_sdk.bridges.redis import RedisBridge
    b = RedisBridge("redis://myhost:6380")
    assert b.redis_url == "redis://myhost:6380"


def test_redis_bridge_queue_backend_raises_when_not_installed():
    from nodus_sdk.bridges import redis as redis_mod
    with patch.object(redis_mod, "_QUEUE_AVAILABLE", False):
        from nodus_sdk.bridges.redis import RedisBridge
        b = RedisBridge("redis://localhost")
        with pytest.raises(ImportError, match="nodus-queue"):
            b.queue_backend()


def test_redis_bridge_event_bus_raises_when_not_installed():
    from nodus_sdk.bridges import redis as redis_mod
    with patch.object(redis_mod, "_EVENTS_AVAILABLE", False):
        from nodus_sdk.bridges.redis import RedisBridge
        b = RedisBridge("redis://localhost")
        with pytest.raises(ImportError, match="nodus-events"):
            b.event_bus()


def test_redis_bridge_queue_backend_when_available():
    try:
        import nodus_queue  # noqa: F401
    except ImportError:
        pytest.skip("nodus-queue not installed")
    from nodus_sdk.bridges.redis import RedisBridge
    b = RedisBridge("redis://localhost:6379")
    # Just instantiating the backend (don't connect)
    backend = b.queue_backend()
    assert backend is not None


def test_redis_bridge_available_true_when_installed():
    try:
        import nodus_queue  # noqa: F401
        import nodus_events  # noqa: F401
    except ImportError:
        pytest.skip("nodus-queue or nodus-events not installed")
    from nodus_sdk.bridges.redis import RedisBridge
    b = RedisBridge("redis://localhost")
    assert b.available() is True
