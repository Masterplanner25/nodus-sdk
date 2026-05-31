"""NodusSDKRuntime — NodusRuntime extended with fluent attach_* bridge methods."""

from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING, Any

from nodus.runtime.embedding import NodusRuntime

if TYPE_CHECKING:
    from nodus_sdk.bridges.sql import SqlBridge
    from nodus_sdk.bridges.vector import VectorBridge
    from nodus_sdk.bridges.scheduler import SchedulerBridge
    from nodus_sdk.bridges.webhook import WebhookBridge


def _available(package: str) -> bool:
    return importlib.util.find_spec(package) is not None


class NodusSDKRuntime(NodusRuntime):
    """NodusRuntime extended with fluent bridge attachment and SDK lifecycle helpers.

    All attach_* methods return self for chaining and are idempotent (a second
    call with the same bridge type is a no-op).
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._attached: set[str] = set()
        self._event_bus: Any = None
        self._auth_key_ring: Any = None

    # ------------------------------------------------------------------
    # Memory bridge (nodus-memory)
    # ------------------------------------------------------------------

    def attach_memory(self, store: Any = None) -> "NodusSDKRuntime":
        if "memory" in self._attached:
            return self
        if store is not None:
            self._memory_store_ref = store
            self._attached.add("memory")
        elif _available("nodus_memory"):
            from nodus_memory import InMemoryStore
            self._memory_store_ref = InMemoryStore()
            self._attached.add("memory")
        return self

    @property
    def memory_store(self) -> Any:
        return getattr(self, "_memory_store_ref", None)

    # ------------------------------------------------------------------
    # Extension bridge (nodus-extension)
    # ------------------------------------------------------------------

    def attach_extension(self, registry: Any = None) -> "NodusSDKRuntime":
        if "extension" in self._attached:
            return self
        if not _available("nodus_extension"):
            return self
        try:
            from nodus_extension.nodus_bindings import attach_to_runtime
            from nodus_extension.registry import ExtensionRegistry
            attach_to_runtime(self, registry or ExtensionRegistry())
        except (ImportError, AttributeError):
            pass
        self._attached.add("extension")
        return self

    # ------------------------------------------------------------------
    # Events bridge (nodus-events) — Python-side reference only
    # ------------------------------------------------------------------

    def attach_events(self, bus: Any = None) -> "NodusSDKRuntime":
        if "events" in self._attached:
            return self
        if bus is None and _available("nodus_events"):
            try:
                from nodus_events.bus import get_event_bus
                bus = get_event_bus()
            except (ImportError, AttributeError):
                pass
        self._event_bus = bus
        self._attached.add("events")
        return self

    @property
    def event_bus(self) -> Any:
        return self._event_bus

    # ------------------------------------------------------------------
    # Auth bridge (nodus-auth) — Python-side reference only
    # ------------------------------------------------------------------

    def attach_auth(self, key_ring: Any = None) -> "NodusSDKRuntime":
        if "auth" in self._attached:
            return self
        if key_ring is None and _available("nodus_auth"):
            try:
                from nodus_auth.tokens import KeyRing
                key_ring = KeyRing.generate()
            except (ImportError, AttributeError):
                pass
        self._auth_key_ring = key_ring
        self._attached.add("auth")
        return self

    @property
    def auth_key_ring(self) -> Any:
        return self._auth_key_ring

    # ------------------------------------------------------------------
    # Observability bridge (nodus-observability)
    # ------------------------------------------------------------------

    def attach_observability(
        self,
        service_name: str | None = None,
        *,
        otel: bool = False,
        prometheus: bool = False,
    ) -> "NodusSDKRuntime":
        if "observability" in self._attached:
            return self
        if not _available("nodus_observability"):
            return self
        from nodus_sdk.bridges.observability import init_observability
        init_observability(
            service_name or "nodus",
            otel=otel,
            prometheus=prometheus,
        )
        self._attached.add("observability")
        return self

    # ------------------------------------------------------------------
    # New Python bridge attach methods
    # ------------------------------------------------------------------

    def attach_sql(self, sql_bridge: "SqlBridge") -> "NodusSDKRuntime":
        if "sql" in self._attached:
            return self
        sql_bridge.register_host_functions(self)
        self._attached.add("sql")
        return self

    def attach_vector(self, vector_bridge: "VectorBridge") -> "NodusSDKRuntime":
        if "vector" in self._attached:
            return self
        vector_bridge.register_host_functions(self)
        self._attached.add("vector")
        return self

    def attach_scheduler(self, scheduler_bridge: "SchedulerBridge") -> "NodusSDKRuntime":
        if "scheduler" in self._attached:
            return self
        scheduler_bridge.register_host_functions(self)
        self._attached.add("scheduler")
        return self

    def attach_webhook(self, webhook_bridge: "WebhookBridge") -> "NodusSDKRuntime":
        if "webhook" in self._attached:
            return self
        webhook_bridge.register_host_functions(self)
        self._attached.add("webhook")
        return self

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def attached_bridges(self) -> frozenset[str]:
        return frozenset(self._attached)
