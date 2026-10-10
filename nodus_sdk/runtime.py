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


def _require(module: str, *names: str) -> tuple[Any, ...]:
    """Import *names* from *module*, loudly.

    Every caller has already checked `_available(pkg)`, so the package *is*
    installed and a missing module or attribute here is a version mismatch
    between this SDK and that package -- not an absent optional dependency.
    The two are opposite situations and the old code could not tell them apart:
    one `except (ImportError, AttributeError): pass` covered both, so

        from nodus_auth.tokens import KeyRing

    -- a module that has never existed in any release of nodus-auth -- was
    indistinguishable from nodus-auth not being installed, and `attach_auth()`
    reported success with nothing attached for the life of the package (#9).
    `attach_events` was broken identically: `get_event_bus` is exported from
    `nodus_events`, never from `nodus_events.bus`.

    Neither was found by reading the code. Both came from running every import
    these methods make, which is why `test_optional_imports_resolve` exists.
    """
    try:
        mod = importlib.import_module(module)
    except ImportError as exc:                      # the module is gone/renamed
        raise ImportError(
            f"{module} is not importable, but its package is installed. "
            f"This is a version mismatch between nodus-sdk and {module.split('.')[0]}, "
            f"not a missing optional dependency: {exc}"
        ) from exc
    missing = [n for n in names if not hasattr(mod, n)]
    if missing:
        raise AttributeError(
            f"{module} does not export {', '.join(missing)}. This is a version "
            f"mismatch between nodus-sdk and {module.split('.')[0]}, not a "
            f"missing optional dependency."
        )
    return tuple(getattr(mod, n) for n in names)


def _is_event_bus_config(value: Any) -> bool:
    """Is *value* a `nodus_events.EventBusConfig` rather than a bus?

    Guarded on availability because a caller can hand `attach_events` any
    object at all when `nodus-events` is not installed, and an isinstance
    against a class we cannot import is not a question that has an answer.
    """
    if not _available("nodus_events"):
        return False
    try:
        (EventBusConfig,) = _require("nodus_events", "EventBusConfig")
    except (ImportError, AttributeError):
        return False
    return isinstance(value, EventBusConfig)


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
        """Install *store* as this runtime's ``std:memory`` store (#7).

        The store a guest's ``memory_put`` / ``memory_get`` reach is the
        runtime's own, isolated per runtime since nodus-lang 5.0.3 and handed
        to every VM as ``vm.memory_store``. This used to set a name nothing
        read (``_memory_store_ref``), so an attached store stayed empty while
        the guest wrote elsewhere -- and ``memory=True`` built a
        ``nodus_memory`` *node* store, a different product that shares a word.

        *store* must be a nodus-lang ``MemoryStore`` (``get``/``put``/
        ``delete``/``keys``/``items``); the runtime falls back to the
        process-global store for anything else, silently, so anything else is
        refused here. ``None`` keeps the runtime's own store, which is already
        isolated: there is nothing to build.
        """
        if "memory" in self._attached:
            return self
        if store is not None:
            from nodus.services.memory_runtime import MemoryStore

            if not isinstance(store, MemoryStore):
                raise TypeError(
                    "attach_memory() takes a nodus.services.memory_runtime.MemoryStore "
                    f"(the std:memory key-value store), got {type(store).__name__}. "
                    "A nodus_memory node store is a different product; it is not what "
                    "memory_get/memory_put read."
                )
            self._memory_store = store
        self._attached.add("memory")
        return self

    @property
    def memory_store(self) -> Any:
        """The store this runtime's guests read and write -- the same object
        ``std:memory`` and the API router's ``/memory/{key}`` use."""
        return self._memory_store

    # ------------------------------------------------------------------
    # Extension bridge (nodus-extension)
    # ------------------------------------------------------------------

    def attach_extension(self, registry: Any = None) -> "NodusSDKRuntime":
        if "extension" in self._attached:
            return self
        if not _available("nodus_extension"):
            return self
        (attach_to_runtime,) = _require(
            "nodus_extension.nodus_bindings", "attach_to_runtime")
        (ExtensionRegistry,) = _require(
            "nodus_extension.registry", "ExtensionRegistry")
        attach_to_runtime(self, registry or ExtensionRegistry())
        self._attached.add("extension")
        return self

    # ------------------------------------------------------------------
    # Events bridge (nodus-events) — Python-side reference only
    # ------------------------------------------------------------------

    def attach_events(self, bus: Any = None) -> "NodusSDKRuntime":
        """Install *bus* as this runtime's event bus, or build the default one.

        `None` with `nodus-events` installed takes its process-wide bus. With
        the package absent there is nothing to build, so nothing is attached
        and `"events"` is **not** recorded -- the old code recorded it either
        way, which made `attached_bridges()` report a bridge that was not
        there (#9).

        An `EventBusConfig` is built into a bus rather than stored as one.
        README has documented `events=EventBusConfig(...)` since 0.1.0 and it
        did not work: the config was assigned to `_event_bus` directly, so
        `rt.event_bus` was a config object with no `publish`. `get_event_bus`
        takes a config, so the documented behaviour was one branch away.

        It also imported `get_event_bus` from `nodus_events.bus`, which does
        not export it; the name is on the package. That `ImportError` was
        swallowed, so every caller got `event_bus is None` and a cheerful
        `"events" in attached_bridges()`.
        """
        if "events" in self._attached:
            return self
        if bus is None or _is_event_bus_config(bus):
            if not _available("nodus_events"):
                return self
            # `nodus_events`, not `nodus_events.bus` -- see the docstring.
            (get_event_bus,) = _require("nodus_events", "get_event_bus")
            bus = get_event_bus(bus)
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
        """Install *key_ring* as this runtime's JWT signing key ring.

        `None` builds one from `AuthSettings().SECRET_KEY`, which is
        nodus-auth's own configuration surface (the `SECRET_KEY` environment
        variable). With `nodus-auth` absent there is nothing to build, so
        nothing is attached and `"auth"` is **not** recorded.

        **It will not invent a signing key**, and that is the decision in this
        method rather than an omission. Two tempting defaults are both wrong:

        - A *random* secret per runtime. Tokens would stop verifying across a
          restart, and across two runtimes in one process, and across the
          replicas of any real deployment -- while working perfectly in the
          single-process test that would have been written for it. That is a
          failure that appears only under the conditions nobody tests.
        - nodus-auth's *dev default* `SECRET_KEY`. It is a published constant,
          so a ring built on it is forgeable by anyone who has read the
          package, and the one thing worse than no auth is auth that looks
          configured.

        So an unconfigured `SECRET_KEY` raises, naming both ways out. Nothing
        can depend on the old behaviour: it attached `None` (#9), because it
        imported `KeyRing` from `nodus_auth.tokens`, a module that has never
        existed in any release -- the real one is `nodus_auth.jwt`, re-exported
        from the package root -- and called `KeyRing.generate()`, which is not a
        classmethod of it. Both errors were swallowed by one `except` clause.

        Requires `nodus-auth>=0.2.0`: 0.1.x signs through `python-jose`, which
        carries an unfixed critical advisory (CVE-2026-85394).
        """
        if "auth" in self._attached:
            return self
        if key_ring is None:
            if not _available("nodus_auth"):
                return self
            # `nodus_auth`, not `nodus_auth.tokens` -- see the docstring.
            KeyRing, AuthSettings = _require("nodus_auth", "KeyRing", "AuthSettings")
            secret = AuthSettings().SECRET_KEY
            if secret == AuthSettings.model_fields["SECRET_KEY"].default:
                # Asked of pydantic rather than compared to a copied literal,
                # so this keeps working when nodus-auth changes its default --
                # which it did in 0.2.0, lengthening it past RFC 7518's floor.
                raise RuntimeError(
                    "attach_auth() will not build a key ring on nodus-auth's "
                    "default SECRET_KEY: it is a published constant, so every "
                    "token signed with it is forgeable. Set the SECRET_KEY "
                    "environment variable to a random secret of at least 32 "
                    "bytes (nodus_auth.generate_key() produces one), or pass "
                    "your own ring: attach_auth(KeyRing(active=...))."
                )
            key_ring = KeyRing(active=secret)
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
