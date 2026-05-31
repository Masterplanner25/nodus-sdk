"""Tests for Phase 1 — NodusSDKRuntime and create_runtime() factory."""

from __future__ import annotations

import importlib.util
from unittest.mock import MagicMock, patch

import pytest

from nodus_sdk import NodusSDKRuntime, create_runtime, detect_available, __version__
from nodus.runtime.embedding import NodusRuntime


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

def test_version_string():
    assert __version__ == "0.1.0"


# ---------------------------------------------------------------------------
# NodusSDKRuntime basics
# ---------------------------------------------------------------------------

def test_sdk_runtime_is_nodus_runtime():
    rt = NodusSDKRuntime(timeout_ms=None)
    assert isinstance(rt, NodusRuntime)


def test_sdk_runtime_run_source_works():
    rt = NodusSDKRuntime(timeout_ms=None)
    result = rt.run_source('print("hello sdk")')
    assert result.get("ok") is True
    assert "hello sdk" in result.get("stdout", "")


def test_sdk_runtime_attached_bridges_empty():
    rt = NodusSDKRuntime(timeout_ms=None)
    assert rt.attached_bridges() == frozenset()


def test_sdk_runtime_attach_sql_registers():
    from nodus_sdk.bridges.sql import SqlBridge
    rt = NodusSDKRuntime(timeout_ms=None)
    bridge = SqlBridge("sqlite:///:memory:")
    ret = rt.attach_sql(bridge)
    assert ret is rt
    assert "sql" in rt.attached_bridges()


def test_sdk_runtime_attach_sql_idempotent():
    from nodus_sdk.bridges.sql import SqlBridge
    rt = NodusSDKRuntime(timeout_ms=None)
    bridge = SqlBridge("sqlite:///:memory:")
    rt.attach_sql(bridge)
    rt.attach_sql(bridge)
    assert "sql" in rt.attached_bridges()


def test_sdk_runtime_attach_webhook_registers():
    from nodus_sdk.bridges.webhook import WebhookBridge
    rt = NodusSDKRuntime(timeout_ms=None)
    bridge = WebhookBridge()
    ret = rt.attach_webhook(bridge)
    assert ret is rt
    assert "webhook" in rt.attached_bridges()


def test_sdk_runtime_fluent_chaining():
    from nodus_sdk.bridges.sql import SqlBridge
    from nodus_sdk.bridges.webhook import WebhookBridge
    rt = (
        NodusSDKRuntime(timeout_ms=None)
        .attach_sql(SqlBridge("sqlite:///:memory:"))
        .attach_webhook(WebhookBridge())
    )
    assert "sql" in rt.attached_bridges()
    assert "webhook" in rt.attached_bridges()


# ---------------------------------------------------------------------------
# create_runtime() factory
# ---------------------------------------------------------------------------

def test_create_runtime_returns_sdk_runtime():
    rt = create_runtime()
    assert isinstance(rt, NodusSDKRuntime)


def test_create_runtime_no_kwargs_works():
    rt = create_runtime()
    result = rt.run_source('print("factory")')
    assert result.get("ok") is True


def test_create_runtime_with_trace_id():
    rt = create_runtime(trace_id="trace-factory-001")
    result = rt.run_source('import "std:identity" as id\nprint(id.trace_id())')
    assert "trace-factory-001" in result.get("stdout", "")


def test_create_runtime_timeout_ms_none():
    rt = create_runtime(timeout_ms=None)
    assert rt.timeout_ms is None


def test_create_runtime_memory_false_no_attachment():
    rt = create_runtime(memory=False)
    assert "memory" not in rt.attached_bridges()


def test_create_runtime_memory_true_when_available():
    if not importlib.util.find_spec("nodus_memory"):
        pytest.skip("nodus-memory not installed")
    rt = create_runtime(memory=True)
    assert "memory" in rt.attached_bridges()
    assert rt.memory_store is not None


def test_create_runtime_memory_false_when_not_installed():
    with patch("nodus_sdk.runtime._available", return_value=False):
        rt = create_runtime(memory=True)
    assert "memory" not in rt.attached_bridges()


def test_create_runtime_extensions_false():
    rt = create_runtime(extensions=False)
    assert "extension" not in rt.attached_bridges()


# ---------------------------------------------------------------------------
# detect_available()
# ---------------------------------------------------------------------------

def test_detect_available_returns_dict():
    avail = detect_available()
    assert isinstance(avail, dict)


def test_detect_available_has_expected_keys():
    avail = detect_available()
    for key in ("memory", "extension", "events", "auth", "observability"):
        assert key in avail


def test_detect_available_values_are_bools():
    avail = detect_available()
    for v in avail.values():
        assert isinstance(v, bool)


def test_detect_available_retry_true():
    avail = detect_available()
    # nodus-retry is a required dep — always available
    assert importlib.util.find_spec("nodus_retry") is not None


# ---------------------------------------------------------------------------
# attach_memory() when package missing
# ---------------------------------------------------------------------------

def test_attach_memory_graceful_when_not_installed():
    rt = NodusSDKRuntime(timeout_ms=None)
    with patch("nodus_sdk.runtime._available", return_value=False):
        ret = rt.attach_memory()
    assert ret is rt
    assert "memory" not in rt.attached_bridges()


# ---------------------------------------------------------------------------
# attach_extension() when package missing
# ---------------------------------------------------------------------------

def test_attach_extension_graceful_when_not_installed():
    rt = NodusSDKRuntime(timeout_ms=None)
    with patch("nodus_sdk.runtime._available", return_value=False):
        ret = rt.attach_extension()
    assert ret is rt
    assert "extension" not in rt.attached_bridges()
