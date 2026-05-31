"""Tests for bridges/api.py — FastAPI router and NodusTraceMiddleware."""

from __future__ import annotations

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from nodus_sdk import create_runtime, NodusSDKRuntime
from nodus_sdk.bridges.api import NodusTraceMiddleware, create_nodus_router


@pytest.fixture
def rt():
    return create_runtime(timeout_ms=None)


@pytest.fixture
def app(rt):
    app = FastAPI()
    app.include_router(create_nodus_router(rt))
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /run
# ---------------------------------------------------------------------------

def test_run_valid_source(client):
    resp = client.post("/run", json={"source": 'print("from api")'})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "from api" in data["stdout"]


def test_run_syntax_error_returns_ok_false(client):
    resp = client.post("/run", json={"source": "let x = "})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert data["error"] is not None


def test_run_runtime_error_returns_ok_false(client):
    resp = client.post("/run", json={"source": 'throw("intentional")'})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "version" in data


def test_health_version_matches(client):
    from nodus.support.version import __version__
    resp = client.get("/health")
    assert resp.json()["version"] == __version__


# ---------------------------------------------------------------------------
# GET /syscalls
# ---------------------------------------------------------------------------

def test_syscalls_returns_list(client):
    resp = client.get("/syscalls")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_syscalls_includes_memory_get(client):
    resp = client.get("/syscalls")
    names = [s["full_name"] for s in resp.json()]
    assert "sys.v1.memory.get" in names


# ---------------------------------------------------------------------------
# Memory endpoints
# ---------------------------------------------------------------------------

def test_memory_write_then_read(client):
    client.post("/memory/test.key", json={"value": "hello"})
    resp = client.get("/memory/test.key")
    assert resp.status_code == 200
    data = resp.json()
    assert data["key"] == "test.key"
    assert data["value"] == "hello"


def test_memory_delete(client):
    client.post("/memory/del.key", json={"value": "x"})
    resp = client.delete("/memory/del.key")
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is True


def test_memory_read_missing_key(client):
    resp = client.get("/memory/no.such.key.xyz")
    assert resp.status_code == 200
    assert resp.json()["value"] is None


# ---------------------------------------------------------------------------
# NodusTraceMiddleware
# ---------------------------------------------------------------------------

def test_trace_middleware_injects_trace_id():
    rt = create_runtime(timeout_ms=None)
    app = FastAPI()
    app.add_middleware(NodusTraceMiddleware, runtime=rt, header="X-Trace-ID")
    app.include_router(create_nodus_router(rt))
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/run",
        json={"source": 'import "std:identity" as id\nprint(id.trace_id())'},
        headers={"X-Trace-ID": "trace-middleware-001"},
    )
    # The middleware sets the runtime trace_id before the request; the .nd code reads it
    data = resp.json()
    assert data["ok"] is True


# ---------------------------------------------------------------------------
# router prefix
# ---------------------------------------------------------------------------

def test_router_with_prefix():
    rt = create_runtime(timeout_ms=None)
    app = FastAPI()
    app.include_router(create_nodus_router(rt, prefix="/api/v1"))
    client = TestClient(app)
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
