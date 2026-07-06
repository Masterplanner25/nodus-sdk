# nodus-sdk

**Unified platform SDK for Nodus AI systems.**

Single-package installation story for the Nodus ecosystem. Auto-wires
available packages via `create_runtime(**kwargs)`, provides 9 bridge modules
for external integrations, and exposes a FastAPI control-plane router.

> **Status:** v0.1.0 — published on [PyPI](https://pypi.org/project/nodus-sdk/).

---

## Install

```bash
pip install nodus-sdk                            # core only
pip install "nodus-sdk[agent,sql,fastapi]"       # agent + SQLAlchemy + FastAPI
pip install "nodus-sdk[full]"                    # everything
```

---

## Quick start

```python
from nodus_sdk import create_runtime

rt = create_runtime(memory=True, trace_id="req-001", timeout_ms=None)
result = rt.run_source('print("hello from sdk")')
```

---

## create_runtime()

```python
from nodus_sdk import create_runtime, NodusSDKRuntime

rt = create_runtime(
    memory=True,          # True = auto-configure; or pass a store object
    events=True,          # True = auto-configure; or pass EventBusConfig
    extensions=True,      # attach ExtensionRegistry
    auth=True,            # attach KeyRing
    observability=True,   # or pass service name string
    trace_id="tid-001",   # injected into every emitted event
    timeout_ms=None,      # None = unlimited (required for long-lived services)
    max_steps=None,
    allowed_paths=None,
    project_root=None,
)
```

`create_runtime` returns a `NodusSDKRuntime` — a `NodusRuntime` subclass with
fluent `attach_*` bridge methods. All capability kwargs accept `True` (default
config) or a config/store object.

---

## NodusSDKRuntime fluent API

```python
from nodus_sdk import NodusSDKRuntime
from nodus_sdk.bridges.sql import SqlBridge
from nodus_sdk.bridges.webhook import WebhookBridge

rt = (
    NodusSDKRuntime(timeout_ms=None)
    .attach_sql(SqlBridge("postgresql://..."))
    .attach_webhook(WebhookBridge(secret="my-secret"))
)
```

All `attach_*` methods are idempotent and return `self`.

---

## Bridges

| Bridge | Install extra | Key class |
|---|---|---|
| `bridges/redis.py` | `[redis]` | `RedisBridge(url)` → queue_backend, event_bus |
| `bridges/http.py` | `[http]` | `HttpBridge()` → NodusHttpClient |
| `bridges/llm.py` | `[llm]` | `LLMBridge(credentials)` → FailoverClient |
| `bridges/observability.py` | `[observability]` | `init_observability(name, otel=, prometheus=)` |
| `bridges/sql.py` | `[sql]` | `SqlBridge(url)` → sql_query/sql_execute host fns |
| `bridges/vector.py` | `[vector]` | `VectorBridge(url, table, dimensions)` → vector_search/upsert/delete |
| `bridges/scheduler.py` | `[scheduler]` | `SchedulerBridge()` → scheduler_add_interval/cron/cancel |
| `bridges/webhook.py` | `[webhooks]` | `WebhookBridge(secret=)` → webhook_send |
| `bridges/api.py` | `[fastapi]` | `create_nodus_router(rt)` + `NodusTraceMiddleware` |

**Bridge return type note:** Bridge host functions return Python maps (dicts),
not Records. Use index access in `.nd` code: `r["status"]`, not `r.status`.

---

## FastAPI integration

```python
from fastapi import FastAPI
from nodus_sdk import create_runtime
from nodus_sdk.bridges.api import create_nodus_router, NodusTraceMiddleware

rt = create_runtime(timeout_ms=None)
app = FastAPI()
app.add_middleware(NodusTraceMiddleware, runtime=rt)
app.include_router(create_nodus_router(rt))
# Routes: POST /run, GET /health, GET /syscalls, GET|POST|DELETE /memory/{key}
```

---

## detect_available()

```python
from nodus_sdk import detect_available

avail = detect_available()
# {"memory": True, "extension": False, "events": True, ...}
```

---

## Development

```bash
pip install -e ".[dev]"
PYTHONPATH="C:/dev/Coding Language/src" pytest tests/ -q
```

Tests require nodus-lang source on `PYTHONPATH`.

---

## License

MIT — see [LICENSE](LICENSE).
