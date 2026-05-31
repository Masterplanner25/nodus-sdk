"""FastAPI bridge — NodusRuntime router and trace middleware."""

from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING, Any, Optional

_FASTAPI_AVAILABLE = importlib.util.find_spec("fastapi") is not None

if TYPE_CHECKING:
    from nodus.runtime.embedding import NodusRuntime

if _FASTAPI_AVAILABLE:
    from pydantic import BaseModel

    class _RunRequest(BaseModel):
        source: str
        timeout_ms: Optional[int] = None

    class _MemoryWriteRequest(BaseModel):
        value: Any


def create_nodus_router(
    runtime: "NodusRuntime",
    *,
    prefix: str = "",
    tags: list[str] | None = None,
    include_memory: bool = True,
    include_syscalls: bool = True,
) -> Any:
    """Return a FastAPI APIRouter with Nodus control-plane endpoints.

    Routes:
      POST  {prefix}/run              — run Nodus source code
      GET   {prefix}/health           — runtime health
      GET   {prefix}/syscalls         — list sys.v1.* syscalls
      GET   {prefix}/memory/{key}     — read from memory store
      POST  {prefix}/memory/{key}     — write to memory store
      DELETE{prefix}/memory/{key}     — delete from memory store

    Requires ``nodus-sdk[fastapi]``.
    """
    if not _FASTAPI_AVAILABLE:
        raise ImportError("fastapi not installed. pip install nodus-sdk[fastapi]")

    from fastapi import APIRouter

    from nodus.support.version import __version__ as nodus_version

    router = APIRouter(prefix=prefix, tags=tags or ["nodus"])

    @router.post("/run")
    def run_source(req: _RunRequest) -> dict:
        result = runtime.run_source(req.source)
        return {
            "ok": result.get("ok", False),
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "error": result.get("error"),
        }

    @router.get("/health")
    def health() -> dict:
        return {"ok": True, "version": nodus_version}

    if include_syscalls:
        @router.get("/syscalls")
        def list_syscalls() -> list:
            try:
                from nodus.services.syscall_runtime import list_syscalls as _list
                return _list()
            except ImportError:
                return []

    if include_memory:
        @router.get("/memory/{key}")
        def memory_get(key: str) -> dict:
            from nodus.services.memory_runtime import get_value
            value = get_value(key)
            return {"key": key, "value": value}

        @router.post("/memory/{key}")
        def memory_set(key: str, req: _MemoryWriteRequest) -> dict:
            from nodus.services.memory_runtime import put_value
            stored = put_value(key, req.value)
            return {"key": key, "value": stored}

        @router.delete("/memory/{key}")
        def memory_delete(key: str) -> dict:
            from nodus.services.memory_runtime import delete_value
            found = delete_value(key)
            return {"key": key, "found": found}

    return router


class NodusTraceMiddleware:
    """ASGI middleware that injects X-Trace-ID into NodusRuntime before each request.

    Usage::

        app = FastAPI()
        rt = create_runtime()
        app.add_middleware(NodusTraceMiddleware, runtime=rt)

    Requires ``nodus-sdk[fastapi]``.
    """

    def __init__(self, app: Any, *, runtime: "NodusRuntime", header: str = "X-Trace-ID") -> None:
        self.app = app
        self.runtime = runtime
        self.header = header.lower().encode()

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            trace_id = None
            for name, value in scope.get("headers", []):
                if name.lower() == self.header:
                    trace_id = value.decode()
                    break
            if trace_id:
                self.runtime.set_trace_id(trace_id)
        await self.app(scope, receive, send)
