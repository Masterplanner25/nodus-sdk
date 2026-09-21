"""Each bridge is exercised by a guest program, not by reading a property (#5, #6, #7).

Three defects shipped green because nothing in this suite ran a `.nd` program
through a bridge: `test_factory.py` asserted `rt.memory_store is not None`,
`test_bridges_api.py` wrote and read through the router only, and the
scheduler tests asserted a job was *listed*. Every test here drives the guest
side and asserts on the host side, or the reverse, so a bridge that reports
success and wires nothing goes red.
"""

from __future__ import annotations

import os
import threading

import pytest

from nodus.services.memory_runtime import MemoryStore
from nodus_sdk import NodusSDKRuntime, create_runtime


# ---------------------------------------------------------------- #6 filesystem jail

ESCAPE = 'import "std:fs" as fs\nprint(fs.write("../escape.txt", "x"))\n'
INSIDE = 'import "std:fs" as fs\nprint(fs.write("inside.txt", "x"))\n'


@pytest.fixture
def cwd_inner(tmp_path):
    inner = tmp_path / "inner"
    inner.mkdir()
    before = os.getcwd()
    os.chdir(inner)
    try:
        yield tmp_path
    finally:
        os.chdir(before)


# closes: #6
def test_create_runtime_jails_the_filesystem_like_a_bare_runtime(cwd_inner):
    result = create_runtime(timeout_ms=None).run_source(ESCAPE)
    assert not (cwd_inner / "escape.txt").exists(), "a write outside the working directory landed"
    assert not result["ok"] and "blocked" in result["error"]["message"], result


def test_a_write_inside_the_jail_still_succeeds(cwd_inner):
    """The control: a jail that refuses everything would pass the test above."""
    result = create_runtime(timeout_ms=None).run_source(INSIDE)
    assert result["ok"], result.get("error")
    assert (cwd_inner / "inner" / "inside.txt").exists()


# closes: #6
def test_an_explicit_none_still_means_unrestricted(cwd_inner):
    """The runtime's own meaning of `None`, for a caller who says so."""
    result = create_runtime(timeout_ms=None, allowed_paths=None).run_source(ESCAPE)
    assert result["ok"], result.get("error")
    assert (cwd_inner / "escape.txt").exists()


# closes: #6
def test_capability_flags_reach_the_runtime():
    denied = create_runtime(timeout_ms=None).run_source('print(env_get("PATH"))')
    assert not denied["ok"] and "allow_env" in denied["error"]["message"], denied
    granted = create_runtime(timeout_ms=None, allow_env=True).run_source('print(env_get("PATH"))')
    assert granted["ok"], granted.get("error")


# ---------------------------------------------------------------- #7 memory

# closes: #7
def test_attach_memory_installs_the_store_the_guest_writes():
    store = MemoryStore()
    rt = NodusSDKRuntime(timeout_ms=None).attach_memory(store)
    result = rt.run_source('memory_put("k", "v")\nprint(memory_get("k"))')
    assert result["ok"] and result["stdout"].strip() == "v", result
    assert store.get("k") == "v", "the guest wrote somewhere other than the attached store"
    assert rt.memory_store is store


# closes: #7
def test_memory_true_means_the_runtimes_own_store():
    rt = create_runtime(memory=True, timeout_ms=None)
    rt.run_source('memory_put("k", "v")')
    assert rt.memory_store.get("k") == "v"


# closes: #7
def test_a_node_store_is_refused_not_ignored():
    class NodeStore:  # the nodus_memory shape: a different product
        def write(self, node): ...
        def search_by_tags(self, *a): ...

    with pytest.raises(TypeError, match="MemoryStore"):
        NodusSDKRuntime(timeout_ms=None).attach_memory(NodeStore())


# closes: #7
def test_the_router_and_the_guest_share_one_store():
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from nodus_sdk.bridges.api import create_nodus_router

    rt = create_runtime(timeout_ms=None)
    app = fastapi.FastAPI()
    app.include_router(create_nodus_router(rt))
    client = TestClient(app)

    client.post("/memory/from.router", json={"value": "r"})
    seen = rt.run_source('print(memory_get("from.router"))')
    assert seen["stdout"].strip() == "r", "the guest cannot see what the router wrote"

    rt.run_source('memory_put("from.guest", "g")')
    assert client.get("/memory/from.guest").json()["value"] == "g", "the router cannot see what the guest wrote"

    assert client.delete("/memory/from.guest").json()["found"] is True
    assert rt.run_source('print(memory_get("from.guest"))')["stdout"].strip() == "nil"


# closes: #7
def test_two_runtimes_stay_isolated_through_their_routers():
    """5.0.3's promise, kept through the SDK: one router per runtime, no sharing."""
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from nodus_sdk.bridges.api import create_nodus_router

    a, b = create_runtime(timeout_ms=None), create_runtime(timeout_ms=None)
    app_a, app_b = fastapi.FastAPI(), fastapi.FastAPI()
    app_a.include_router(create_nodus_router(a))
    app_b.include_router(create_nodus_router(b))
    TestClient(app_a).post("/memory/only.a", json={"value": 1})
    assert TestClient(app_b).get("/memory/only.a").json()["value"] is None
    assert b.run_source('print(memory_get("only.a"))')["stdout"].strip() == "nil"


# ---------------------------------------------------------------- #5 scheduler

# closes: #5
def test_a_guest_scheduled_job_actually_runs():
    pytest.importorskip("apscheduler")
    from nodus_sdk.bridges.scheduler import SchedulerBridge

    fired = threading.Event()
    control = threading.Event()
    bridge = SchedulerBridge().register_job("work", fired.set)
    bridge.start()
    try:
        # Control: APScheduler fires in this environment at all.
        bridge.add_interval_job("ctrl", control.set, seconds=1)
        rt = NodusSDKRuntime(timeout_ms=None).attach_scheduler(bridge)
        result = rt.run_source('print(scheduler_add_interval("guest.job", 1, "work"))')
        assert result["ok"] and result["stdout"].strip() == "guest.job", result
        assert control.wait(10), "control job never fired: the scheduler itself is not running"
        assert fired.wait(10), "the guest-scheduled job never ran (#5: it used to schedule lambda: None)"
    finally:
        bridge.shutdown(wait=False)


# closes: #5
def test_an_unregistered_job_name_is_refused_not_scheduled():
    pytest.importorskip("apscheduler")
    from nodus_sdk.bridges.scheduler import SchedulerBridge

    bridge = SchedulerBridge()
    bridge.start()
    try:
        rt = NodusSDKRuntime(timeout_ms=None).attach_scheduler(bridge)
        result = rt.run_source('print(scheduler_add_interval("guest.job", 1, "nobody"))')
        assert result["stdout"].startswith("error:unknown job 'nobody'"), result["stdout"]
        assert bridge.list_jobs() == [], "a job was scheduled for a name nothing will run"
    finally:
        bridge.shutdown(wait=False)


# closes: #5
def test_cron_takes_a_registered_job_too():
    pytest.importorskip("apscheduler")
    from nodus_sdk.bridges.scheduler import SchedulerBridge

    bridge = SchedulerBridge().register_job("nightly", lambda: None)
    bridge.start()
    try:
        rt = NodusSDKRuntime(timeout_ms=None).attach_scheduler(bridge)
        ok = rt.run_source('print(scheduler_add_cron("n", "0 3 * * *", "nightly"))')
        bad = rt.run_source('print(scheduler_add_cron("m", "0 3 * * *", "missing"))')
        assert ok["stdout"].strip() == "n", ok
        assert bad["stdout"].startswith("error:unknown job"), bad["stdout"]
        assert [j["id"] for j in bridge.list_jobs()] == ["n"]
    finally:
        bridge.shutdown(wait=False)
