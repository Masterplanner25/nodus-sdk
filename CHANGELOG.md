# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [0.1.0] — 2026-05-31

Initial release — prepared, not yet published.

### Added

- **`NodusSDKRuntime`** — `NodusRuntime` subclass with fluent `attach_*`
  bridge methods. All methods are idempotent and return `self` for chaining.
  `attach_memory`, `attach_extension`, `attach_events`, `attach_auth`,
  `attach_observability`, `attach_sql`, `attach_vector`, `attach_scheduler`,
  `attach_webhook`. `attached_bridges()` → frozenset of attached bridge names.

- **`create_runtime(**kwargs)`** — factory that constructs and auto-wires a
  `NodusSDKRuntime`. Kwargs: `memory`, `events`, `extensions`, `auth`,
  `observability`, `trace_id`, `timeout_ms`, `max_steps`, `allowed_paths`,
  `project_root`. Each accepts `True` (default config) or a config/store object.

- **`detect_available()`** — surveys installed optional packages via
  `importlib.util.find_spec` and returns a `dict[str, bool]`.

- **9 bridge modules:**
  - `bridges/redis.py` — `RedisBridge`: `queue_backend()`, `event_bus()`
  - `bridges/http.py` — `HttpBridge`: `client()` → NodusHttpClient
  - `bridges/llm.py` — `LLMBridge`: `failover_client(provider_fn)` (requires provider_fn)
  - `bridges/observability.py` — `init_observability(name, otel=, prometheus=)`
  - `bridges/sql.py` — `SqlBridge(url)`: `session()`, `execute()`,
    `register_host_functions()` → `sql_query`, `sql_execute` host fns
  - `bridges/vector.py` — `VectorBridge(url, table, dimensions)`:
    `ensure_table()`, `upsert()`, `search()`, `delete()`,
    `register_host_functions()` → `vector_upsert`, `vector_search`, `vector_delete`
  - `bridges/scheduler.py` — `SchedulerBridge()`: `start()`, `shutdown()`,
    `add_interval_job()`, `add_cron_job()`, `cancel()`, `list_jobs()`,
    `register_host_functions()` → `scheduler_add_interval/cron/cancel/list_jobs`
  - `bridges/webhook.py` — `WebhookBridge(secret=)`: `send()`, `send_async()`,
    `register_host_functions()` → `webhook_send`
  - `bridges/api.py` — `create_nodus_router(rt)` FastAPI router:
    POST /run, GET /health, GET /syscalls, GET|POST|DELETE /memory/{key}.
    `NodusTraceMiddleware`: reads `X-Trace-ID` header → `set_trace_id()`.

- **Bridge return type:** host functions return Python maps (dicts), not Records.
  `.nd` code must use `r["key"]` not `r.key`.

- **Required dependencies:** `nodus-lang>=4.1.0`, `nodus-schema>=0.1.0`,
  `nodus-protocol>=0.1.0`, `nodus-retry>=0.1.0`.

- **Extras:** `agent`, `workflow`, `memory`, `auth`, `llm`, `http`, `redis`,
  `sql`, `vector`, `scheduler`, `fastapi`, `webhooks`, `observability`,
  `extensions`, `full`.

- **99 tests** across 10 test files.

[0.1.0]: https://github.com/Masterplanner25/nodus-sdk/releases/tag/v0.1.0
