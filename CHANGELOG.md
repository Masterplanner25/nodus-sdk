# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

## [0.1.3] — 2026-09-20

Three bridges reported success and did nothing. Each shipped green because
nothing in the suite ran a `.nd` program through it; `tests/test_bridges_reach_
the_guest.py` now drives every one of them from the guest side.

### Fixed

- **`create_runtime()` built a runtime with no filesystem jail** (#6). It passed
  `allowed_paths=None` explicitly, which `NodusRuntime` reads as *unrestricted*,
  while a bare `NodusRuntime()` jails to the working directory. Measured: a
  guest's `fs.write("../escape.txt")` landed. The argument is now omitted unless
  given — the runtime's own default applies — and an explicit `None` still
  means no jail, for a caller who says so. `allow_subprocess`, `allow_network`
  and `allow_env` are new keyword-only flags (default `False`, passed only when
  granted, so the `nodus-lang>=4.0.0` floor is unchanged).
- **The memory bridge was disconnected from the store guests use** (#7), three
  ways. `attach_memory(store)` set `_memory_store_ref`, a name nothing reads,
  so the attached store stayed empty while the guest wrote to the runtime's
  own; `create_nodus_router(rt)`'s `/memory/{key}` routes used the
  **process-global** store, which no guest of an isolated runtime has seen
  since nodus-lang 5.0.3; and `memory=True` built a `nodus_memory` *node*
  store — a different product that shares a word with `std:memory`. Now:
  `attach_memory` installs a nodus-lang `MemoryStore` as the runtime's store
  (anything else is refused with a `TypeError` naming the mismatch, because the
  runtime silently falls back to the global store for a non-`MemoryStore`);
  `memory=True` means the runtime's own already-isolated store and needs no
  optional package; the router reads and writes that same store; and
  `rt.memory_store` returns it.
- **`scheduler_add_interval` / `scheduler_add_cron` scheduled a no-op** (#5).
  They passed `lambda: None` as the callback: the job id came back, the job
  listed, `next_run` advanced, and nothing ever ran. A `.nd` program now
  schedules work by naming a job the host registered with
  `SchedulerBridge.register_job(name, fn)` — a third argument to both builtins
  — and the callback runs host-side on the APScheduler thread, where
  re-entering the VM would not be safe. A name nothing registered is refused
  at scheduling time (`error:unknown job …`), not scheduled inert.

### Changed

- `scheduler_add_interval(job_id, seconds, job)` and
  `scheduler_add_cron(job_id, cron_expr, job)` take three arguments (were two).
  The two-argument form never did anything, so nothing that *worked* breaks.
- `attach_memory()` with a `nodus_memory` store raises instead of accepting it.
  It was never wired to anything a guest could reach.


---

## [0.1.2] — 2026-08-17

### Changed

- **Floated the `nodus-lang` dependency to `>=4.0.0`**, reversing the `<5.0.0`
  cap added in 0.1.1. That cap was added to guard against "a future nodus-lang
  5.x that could break the SDK's bridge wiring." 5.0.0 shipped on 2026-08-17 and
  broke nothing here — the full suite passes against it unchanged — but the cap
  made the package uninstallable alongside it (`ResolutionImpossible`), which is
  the more expensive failure of the two, and one that no test could have caught.

  A hard upper bound on a first-party dependency turns every nodus-lang major
  into a two-repo release train with consumers frozen in between. This package's
  own suite is the check that catches a real break; a cap earns its place once a
  break is known.

### Fixed

- **`test_version_string` asserted `0.1.0`** while the package had been `0.1.1`
  since 2026-07-12, so the suite shipped one guaranteed failure. Now asserts the
  current version.

---

## [0.1.1] — 2026-07-12

### Changed

- **Capped the `nodus-lang` dependency at `<5.0.0`** (was unbounded `>=4.0.0`).
  Guards against `pip` resolving a future `nodus-lang` 5.x that could break the
  SDK's bridge wiring; the published 0.1.0 lacked the upper bound. No API change.

---

## [0.1.0] — 2026-05-31

Initial release.

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
