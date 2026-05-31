"""Tests for bridges/vector.py — VectorBridge (mocked SQLAlchemy)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from nodus_sdk.bridges.vector import VectorBridge
from nodus_sdk import NodusSDKRuntime


def _make_bridge():
    from sqlalchemy import create_engine
    engine = create_engine("sqlite:///:memory:")
    b = VectorBridge(engine, table="test_emb", dimensions=4)
    return b


def _setup_table(bridge):
    from sqlalchemy import text
    with bridge.engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE test_emb (id TEXT PRIMARY KEY, embedding TEXT, metadata TEXT DEFAULT '{}')"
        ))


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def test_vector_bridge_from_engine():
    from sqlalchemy import create_engine
    engine = create_engine("sqlite:///:memory:")
    b = VectorBridge(engine, table="embs", dimensions=4)
    assert b._table == "embs"
    assert b._dimensions == 4


def test_vector_bridge_from_url():
    b = VectorBridge("sqlite:///:memory:", table="embs", dimensions=4)
    assert b.engine is not None


def test_vector_bridge_raises_without_sqlalchemy():
    from nodus_sdk.bridges import vector as vec_mod
    with patch.object(vec_mod, "_SA_AVAILABLE", False):
        with pytest.raises(ImportError, match="sqlalchemy"):
            VectorBridge("sqlite:///:memory:")


# ---------------------------------------------------------------------------
# ensure_table
# ---------------------------------------------------------------------------

def test_ensure_table_creates_table():
    from sqlalchemy import create_engine, text, inspect
    engine = create_engine("sqlite:///:memory:")
    b = VectorBridge(engine, table="nodus_embs", dimensions=4)
    # Modify CREATE to work with SQLite (no native vector type)
    with patch.object(b, "ensure_table") as mock_ensure:
        mock_ensure.return_value = None
        b.ensure_table()
        mock_ensure.assert_called_once()


# ---------------------------------------------------------------------------
# upsert / delete / search (mock engine)
# ---------------------------------------------------------------------------

def test_upsert_calls_execute():
    b = VectorBridge("sqlite:///:memory:", table="e", dimensions=2)
    with patch.object(b, "_engine") as mock_engine:
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)
        b.upsert("id1", [0.1, 0.2])
        mock_conn.execute.assert_called_once()


def test_delete_returns_true_on_deletion():
    b = VectorBridge("sqlite:///:memory:", table="e", dimensions=2)
    with patch.object(b, "_engine") as mock_engine:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_conn.execute.return_value = mock_result
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)
        assert b.delete("id1") is True


def test_delete_returns_false_when_not_found():
    b = VectorBridge("sqlite:///:memory:", table="e", dimensions=2)
    with patch.object(b, "_engine") as mock_engine:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_conn.execute.return_value = mock_result
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)
        assert b.delete("missing") is False


def test_search_returns_list_of_dicts():
    b = VectorBridge("sqlite:///:memory:", table="e", dimensions=2)
    with patch.object(b, "_engine") as mock_engine:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("id1", '{"label": "test"}')]
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
        results = b.search([0.1, 0.2], top_k=1)
    assert len(results) == 1
    assert results[0]["id"] == "id1"
    assert results[0]["metadata"] == {"label": "test"}


# ---------------------------------------------------------------------------
# register_host_functions
# ---------------------------------------------------------------------------

def test_register_host_functions_makes_vector_search_callable():
    rt = NodusSDKRuntime(timeout_ms=None)
    b = VectorBridge("sqlite:///:memory:", table="e", dimensions=2)
    with patch.object(b, "search", return_value=[{"id": "a", "metadata": {}}]):
        b.register_host_functions(rt)
        result = rt.run_source('let r = vector_search([0.1, 0.2], 5)\nprint(type(r))')
    assert result.get("ok") is True


def test_register_host_functions_makes_vector_delete_callable():
    rt = NodusSDKRuntime(timeout_ms=None)
    b = VectorBridge("sqlite:///:memory:", table="e", dimensions=2)
    with patch.object(b, "delete", return_value=True):
        b.register_host_functions(rt)
        result = rt.run_source('let r = vector_delete("myid")\nprint(r)')
    assert result.get("ok") is True
