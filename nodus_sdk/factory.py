"""create_runtime() — auto-wired NodusSDKRuntime factory."""

from __future__ import annotations

import importlib.util
from typing import Any

from nodus_sdk.runtime import NodusSDKRuntime


def _available(package: str) -> bool:
    return importlib.util.find_spec(package) is not None


def detect_available() -> dict[str, bool]:
    """Return a map of optional package availability."""
    return {
        "memory": _available("nodus_memory"),
        "extension": _available("nodus_extension"),
        "events": _available("nodus_events"),
        "auth": _available("nodus_auth"),
        "observability": _available("nodus_observability"),
        "agent": _available("nodus_agent"),
        "workflow": _available("nodus_workflow"),
        "llm": _available("nodus_llm"),
        "http": _available("nodus_http"),
        "queue": _available("nodus_queue"),
        "circuit_breaker": _available("nodus_circuit_breaker"),
    }


class _Unset:
    """`allowed_paths` was not given (#6).

    `NodusRuntime` reads an explicit ``None`` as *unrestricted* and has its own
    sentinel for "the caller said nothing" (jail to the working directory).
    The factory used to default to ``None`` and pass it through, so
    ``create_runtime()`` built a runtime with no filesystem jail while a bare
    ``NodusRuntime()`` had one. Unset here means the argument is omitted and
    the runtime's own default applies; ``None`` is still passed through as the
    runtime's "unrestricted", for a caller who says so.
    """

    def __repr__(self) -> str:
        return "UNSET"


_UNSET: Any = _Unset()


def create_runtime(
    *,
    memory: bool | Any = False,
    events: bool | Any = False,
    extensions: bool = False,
    auth: bool | Any = False,
    observability: bool | str = False,
    trace_id: str | None = None,
    timeout_ms: int | None = None,
    max_steps: int | None = None,
    allowed_paths: list[str] | None = _UNSET,
    project_root: str | None = None,
    allow_input: bool = False,
    allow_subprocess: bool = False,
    allow_network: bool = False,
    allow_env: bool = False,
    max_frames: int | None = None,
) -> NodusSDKRuntime:
    """Create a pre-wired NodusSDKRuntime.

    Each capability kwarg accepts either a bool (True = auto-configure with defaults)
    or a config/store object for custom configuration.

    Confinement matches a bare ``NodusRuntime``: the filesystem is jailed to the
    working directory unless ``allowed_paths`` is given (``None`` = no jail),
    and subprocess, network and environment access are denied unless the
    matching ``allow_*`` flag is ``True``.

    Example::

        rt = create_runtime(memory=True, trace_id="abc-123", timeout_ms=None)
        rt = create_runtime(memory=my_store, auth=my_key_ring, observability="my-service")
        rt = create_runtime(allow_network=True, allowed_paths=["/data"])
    """
    kwargs: dict[str, Any] = dict(
        timeout_ms=timeout_ms,
        max_steps=max_steps,
        project_root=project_root,
        allow_input=allow_input,
        max_frames=max_frames,
    )
    if allowed_paths is not _UNSET:
        kwargs["allowed_paths"] = allowed_paths
    # Passed only when granted, so the runtime's own defaults hold otherwise.
    for flag, value in (("allow_subprocess", allow_subprocess), ("allow_network", allow_network), ("allow_env", allow_env)):
        if value:
            kwargs[flag] = True
    rt = NodusSDKRuntime(**kwargs)

    if trace_id is not None:
        rt.set_trace_id(trace_id)

    if memory is not False:
        store = None if memory is True else memory
        rt.attach_memory(store)

    if events is not False:
        bus = None if events is True else events
        rt.attach_events(bus)

    if extensions:
        rt.attach_extension()

    if auth is not False:
        key_ring = None if auth is True else auth
        rt.attach_auth(key_ring)

    if observability is not False:
        service_name = "nodus" if observability is True else str(observability)
        rt.attach_observability(service_name)

    return rt
