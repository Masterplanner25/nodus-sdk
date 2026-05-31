"""Tests for bridges/scheduler.py — SchedulerBridge."""

from __future__ import annotations

import pytest

from nodus_sdk.bridges.scheduler import SchedulerBridge
from nodus_sdk import NodusSDKRuntime


@pytest.fixture
def bridge():
    b = SchedulerBridge(timezone="UTC", max_workers=2)
    yield b
    if b._started:
        b.shutdown(wait=False)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def test_scheduler_bridge_creates():
    b = SchedulerBridge()
    assert b._scheduler is not None


def test_scheduler_bridge_raises_without_apscheduler():
    from nodus_sdk.bridges import scheduler as sched_mod
    from unittest.mock import patch
    with patch.object(sched_mod, "_AVAILABLE", False):
        with pytest.raises(ImportError, match="apscheduler"):
            SchedulerBridge()


# ---------------------------------------------------------------------------
# start / shutdown
# ---------------------------------------------------------------------------

def test_start_and_shutdown(bridge):
    bridge.start()
    assert bridge._started is True
    bridge.shutdown(wait=False)
    assert bridge._started is False


def test_start_idempotent(bridge):
    bridge.start()
    bridge.start()
    assert bridge._started is True
    bridge.shutdown(wait=False)


# ---------------------------------------------------------------------------
# add_interval_job
# ---------------------------------------------------------------------------

def test_add_interval_job(bridge):
    bridge.start()
    job = bridge.add_interval_job("test.interval", lambda: None, seconds=60)
    assert job is not None
    assert job.id == "test.interval"


def test_add_cron_job(bridge):
    bridge.start()
    job = bridge.add_cron_job("test.cron", lambda: None, cron_expr="0 * * * *")
    assert job is not None
    assert job.id == "test.cron"


# ---------------------------------------------------------------------------
# cancel
# ---------------------------------------------------------------------------

def test_cancel_existing_job(bridge):
    bridge.start()
    bridge.add_interval_job("cancel.me", lambda: None, seconds=60)
    result = bridge.cancel("cancel.me")
    assert result is True


def test_cancel_nonexistent_returns_false(bridge):
    bridge.start()
    result = bridge.cancel("does.not.exist")
    assert result is False


# ---------------------------------------------------------------------------
# list_jobs
# ---------------------------------------------------------------------------

def test_list_jobs_returns_list(bridge):
    bridge.start()
    bridge.add_interval_job("list.test", lambda: None, seconds=60)
    jobs = bridge.list_jobs()
    assert isinstance(jobs, list)
    assert any(j["id"] == "list.test" for j in jobs)


# ---------------------------------------------------------------------------
# register_host_functions
# ---------------------------------------------------------------------------

def test_register_host_functions_scheduler_add_interval(bridge):
    bridge.start()
    rt = NodusSDKRuntime(timeout_ms=None)
    bridge.register_host_functions(rt)
    result = rt.run_source('let r = scheduler_add_interval("nd.job", 60i)\nprint(r)')
    assert result.get("ok") is True
    assert "nd.job" in result.get("stdout", "")


def test_register_host_functions_scheduler_cancel(bridge):
    bridge.start()
    rt = NodusSDKRuntime(timeout_ms=None)
    bridge.register_host_functions(rt)
    result = rt.run_source('let r = scheduler_cancel("nonexistent")\nprint(r)')
    assert result.get("ok") is True
    assert "false" in result.get("stdout", "")


def test_scheduler_list_jobs_callable_from_nd(bridge):
    bridge.start()
    bridge.add_interval_job("nd.listed", lambda: None, seconds=60)
    rt = NodusSDKRuntime(timeout_ms=None)
    bridge.register_host_functions(rt)
    result = rt.run_source('let jobs = scheduler_list_jobs()\nprint(len(jobs))')
    assert result.get("ok") is True
