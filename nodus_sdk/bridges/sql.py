"""SqlBridge — SQLAlchemy 2.x session bridge with Nodus host function registration."""

from __future__ import annotations

import importlib.util
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Generator

_AVAILABLE = importlib.util.find_spec("sqlalchemy") is not None

if TYPE_CHECKING:
    from nodus.runtime.embedding import NodusRuntime
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session


class SqlBridge:
    """SQLAlchemy bridge that registers sql_* host functions on a NodusRuntime.

    Requires ``nodus-sdk[sql]`` (``sqlalchemy>=2.0``).

    Usage::

        bridge = SqlBridge("sqlite:///mydb.db")
        rt = create_runtime()
        rt.attach_sql(bridge)
        # Now .nd code can call: sql_query("SELECT ...", {}) → list
    """

    def __init__(
        self,
        engine_or_url: "str | Engine",
        *,
        echo: bool = False,
        pool_size: int = 5,
    ) -> None:
        if not _AVAILABLE:
            raise ImportError("sqlalchemy not installed. pip install nodus-sdk[sql]")
        from sqlalchemy import create_engine
        from sqlalchemy.engine import Engine as _Engine

        if isinstance(engine_or_url, _Engine):
            self._engine = engine_or_url
        else:
            url = str(engine_or_url)
            kwargs: dict[str, Any] = {"echo": echo}
            if not url.startswith("sqlite"):
                kwargs["pool_size"] = pool_size
            self._engine = create_engine(url, **kwargs)

        self._tx_sessions: dict[str, Any] = {}

    @contextmanager
    def session(self) -> Generator["Session", None, None]:
        """Yield a SQLAlchemy Session that commits on clean exit and rolls back on error."""
        from sqlalchemy.orm import Session as _Session
        with _Session(self._engine) as s:
            try:
                yield s
                s.commit()
            except Exception:
                s.rollback()
                raise

    def execute(self, sql: str, params: dict | None = None) -> list[dict]:
        """Execute a SELECT and return results as a list of dicts."""
        from sqlalchemy import text
        with self.session() as s:
            result = s.execute(text(sql), params or {})
            keys = list(result.keys())
            return [dict(zip(keys, row)) for row in result.fetchall()]

    def register_host_functions(self, runtime: "NodusRuntime") -> None:
        """Register sql_query, sql_execute host functions on the runtime."""
        bridge = self

        def sql_query(sql: str, params: Any = None) -> list:
            if not isinstance(sql, str):
                return []
            p = dict(params.fields) if hasattr(params, "fields") else (params or {})
            try:
                return bridge.execute(sql, p)
            except Exception as exc:
                return [{"__error__": str(exc)}]

        def sql_execute(sql: str, params: Any = None) -> int:
            if not isinstance(sql, str):
                return 0
            from sqlalchemy import text
            p = dict(params.fields) if hasattr(params, "fields") else (params or {})
            try:
                with bridge.session() as s:
                    result = s.execute(text(sql), p)
                    return result.rowcount
            except Exception:
                return -1

        runtime.register_function("sql_query", sql_query, arity=2)
        runtime.register_function("sql_execute", sql_execute, arity=2)

    @property
    def engine(self) -> "Engine":
        return self._engine
