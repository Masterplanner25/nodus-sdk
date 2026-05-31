"""RedisBridge — unified bridge over nodus-queue and nodus-events."""

from __future__ import annotations

import importlib.util
from typing import Any

_QUEUE_AVAILABLE = importlib.util.find_spec("nodus_queue") is not None
_EVENTS_AVAILABLE = importlib.util.find_spec("nodus_events") is not None


class RedisBridge:
    """Thin bridge wrapping nodus-queue and nodus-events for a single Redis URL.

    Requires ``nodus-sdk[redis]`` (``nodus-queue[redis]`` + ``nodus-events[redis]``).
    """

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url

    def available(self) -> bool:
        return _QUEUE_AVAILABLE and _EVENTS_AVAILABLE

    def queue_backend(self) -> Any:
        """Return a RedisQueueBackend connected to this bridge's Redis URL."""
        if not _QUEUE_AVAILABLE:
            raise ImportError("nodus-queue not installed. pip install nodus-sdk[redis]")
        from nodus_queue import RedisQueueBackend
        return RedisQueueBackend(self._redis_url)

    def event_bus(self, *, channel: str = "nodus:events") -> Any:
        """Return an EventBus connected to this bridge's Redis URL."""
        if not _EVENTS_AVAILABLE:
            raise ImportError("nodus-events not installed. pip install nodus-sdk[redis]")
        from nodus_events import EventBus, EventBusConfig
        config = EventBusConfig(redis_url=self._redis_url, channel=channel)
        return EventBus(config)

    @property
    def redis_url(self) -> str:
        return self._redis_url
