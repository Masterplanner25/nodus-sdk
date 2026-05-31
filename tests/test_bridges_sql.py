"""Tests for bridges/sql.py — SqlBridge (SQLite in-memory)."""

from __future__ import annotations

import pytest

from nodus_sdk.bridges.sql import SqlBridge
from nodus_sdk import NodusSDKRuntime


@pytest.fixture
def bridge():
    return SqlBridge("sqlite:///:memory:")


@pytest.fixture
def table_bridge():
    b = SqlBridge("sqlite:///:memory:")
    with b.session() as s:
        from sqlalchemy import text
        s.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)"))
        s.execute(text("INSERT INTO users VALUES (1, 'Alice')"))
        s.execute(text("INSERT INTO users VALUES (2, 'Bob')"))
    return b


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def test_sql_bridge_creates_engine():
    b = SqlBridge("sqlite:///:memory:")
    assert b.engine is not None


def test_sql_bridge_from_string_url():
    b = SqlBridge("sqlite://")
    assert b.engine is not None


# ---------------------------------------------------------------------------
# session()
# ---------------------------------------------------------------------------

def test_session_yields_and_commits(bridge):
    with bridge.session() as s:
        from sqlalchemy import text
        s.execute(text("CREATE TABLE t (x INTEGER)"))
        s.execute(text("INSERT INTO t VALUES (42)"))
    # After context, table should exist and have data
    rows = bridge.execute("SELECT x FROM t")
    assert rows == [{"x": 42}]


def test_session_rolls_back_on_error(bridge):
    with bridge.session() as s:
        from sqlalchemy import text
        s.execute(text("CREATE TABLE rollback_test (x INTEGER)"))
    try:
        with bridge.session() as s:
            from sqlalchemy import text
            s.execute(text("INSERT INTO rollback_test VALUES (99)"))
            raise RuntimeError("forced error")
    except RuntimeError:
        pass
    rows = bridge.execute("SELECT x FROM rollback_test")
    assert rows == []


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------

def test_execute_returns_list_of_dicts(table_bridge):
    rows = table_bridge.execute("SELECT id, name FROM users ORDER BY id")
    assert rows == [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]


def test_execute_with_params(table_bridge):
    rows = table_bridge.execute("SELECT name FROM users WHERE id = :uid", {"uid": 2})
    assert rows == [{"name": "Bob"}]


def test_execute_empty_result(table_bridge):
    rows = table_bridge.execute("SELECT * FROM users WHERE id = 999")
    assert rows == []


# ---------------------------------------------------------------------------
# register_host_functions()
# ---------------------------------------------------------------------------

def test_register_host_functions_registers_sql_query(table_bridge):
    rt = NodusSDKRuntime(timeout_ms=None)
    table_bridge.register_host_functions(rt)
    result = rt.run_source('let rows = sql_query("SELECT name FROM users WHERE id = :uid", {})\nprint(len(rows))')
    assert result.get("ok") is True


def test_sql_query_callable_from_nd(table_bridge):
    rt = NodusSDKRuntime(timeout_ms=None)
    table_bridge.register_host_functions(rt)
    result = rt.run_source('''
let rows = sql_query("SELECT id, name FROM users ORDER BY id", {})
print(len(rows))
''')
    assert result.get("ok") is True
    assert "2" in result.get("stdout", "")


def test_sql_execute_callable_from_nd(bridge):
    with bridge.session() as s:
        from sqlalchemy import text
        s.execute(text("CREATE TABLE ex_test (val TEXT)"))
    rt = NodusSDKRuntime(timeout_ms=None)
    bridge.register_host_functions(rt)
    result = rt.run_source('let n = sql_execute("INSERT INTO ex_test VALUES (:v)", {})\nprint(n)')
    assert result.get("ok") is True


def test_sql_query_returns_list_not_exception(table_bridge):
    rt = NodusSDKRuntime(timeout_ms=None)
    table_bridge.register_host_functions(rt)
    # Bad SQL should return error dict, not raise
    result = rt.run_source('let r = sql_query("SELECT * FROM nonexistent", {})\nprint(type(r))')
    assert result.get("ok") is True


# ---------------------------------------------------------------------------
# Parameterized queries
# ---------------------------------------------------------------------------

def test_parameterized_select(table_bridge):
    rows = table_bridge.execute(
        "SELECT name FROM users WHERE name LIKE :pat",
        {"pat": "Ali%"},
    )
    assert rows == [{"name": "Alice"}]
