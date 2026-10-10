"""Tests for Phase 1 — NodusSDKRuntime and create_runtime() factory."""

from __future__ import annotations

import importlib.util
import pathlib
from unittest.mock import patch

import pytest

from nodus_sdk import NodusSDKRuntime, create_runtime, detect_available, __version__
from nodus.runtime.embedding import NodusRuntime


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

def test_version_string():
    assert __version__ == "0.2.0"


def test_pyproject_and_version_module_agree():
    """Two files carry this version and nothing compared them.

    `_version.py` is what `nodus_sdk.__version__` reports and `pyproject.toml`
    is what pip installs as; they are edited by hand, together, at every
    release. A mismatch publishes a wheel whose metadata disagrees with the
    package inside it -- and the test above pins only one of the two, so it
    would stay green.
    """
    import re

    text = (pathlib.Path(__file__).resolve().parent.parent
            / "pyproject.toml").read_text(encoding="utf-8")
    declared = re.search(r'^version = "([^"]+)"', text, re.MULTILINE)
    assert declared, "pyproject.toml has no top-level version"
    assert declared.group(1) == __version__, (
        f"pyproject.toml says {declared.group(1)}, "
        f"nodus_sdk.__version__ says {__version__}"
    )


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


def test_create_runtime_memory_needs_no_optional_package():
    # #7: `memory=True` is the runtime's own std:memory store, which every
    # runtime has. It used to depend on nodus_memory being installed -- and
    # then built a node store that memory_get could never read.
    with patch("nodus_sdk.runtime._available", return_value=False):
        rt = create_runtime(memory=True, timeout_ms=None)
    assert "memory" in rt.attached_bridges()
    rt.run_source('memory_put("k", 1i)')
    assert rt.memory_store.get("k") == 1


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


def test_nodus_retry_is_a_required_dependency():
    """Named for what it asserts.

    It was `test_detect_available_retry_true`, called `detect_available()`,
    threw the result away, and checked `find_spec` instead -- so it tested
    nothing about `detect_available`. It could not have: that map has no
    `retry` key, because nodus-retry is a hard dependency rather than an
    optional one, which is what this actually pins.
    """
    assert importlib.util.find_spec("nodus_retry") is not None
    assert "retry" not in detect_available(), (
        "nodus-retry became optional; this test and detect_available() need to "
        "agree on which it is"
    )


# ---------------------------------------------------------------------------
# attach_memory() when package missing
# ---------------------------------------------------------------------------

def test_attach_memory_without_a_store_keeps_the_runtimes_own():
    rt = NodusSDKRuntime(timeout_ms=None)
    own = rt.memory_store
    with patch("nodus_sdk.runtime._available", return_value=False):
        ret = rt.attach_memory()
    assert ret is rt
    assert "memory" in rt.attached_bridges()
    assert rt.memory_store is own


# ---------------------------------------------------------------------------
# attach_extension() when package missing
# ---------------------------------------------------------------------------

def test_attach_extension_graceful_when_not_installed():
    rt = NodusSDKRuntime(timeout_ms=None)
    with patch("nodus_sdk.runtime._available", return_value=False):
        ret = rt.attach_extension()
    assert ret is rt
    assert "extension" not in rt.attached_bridges()
