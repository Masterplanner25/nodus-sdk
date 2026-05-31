"""VectorBridge — pgvector + SQLAlchemy semantic search bridge."""

from __future__ import annotations

import importlib.util
import json
from typing import TYPE_CHECKING, Any

_SA_AVAILABLE = importlib.util.find_spec("sqlalchemy") is not None
_PG_AVAILABLE = importlib.util.find_spec("pgvector") is not None
_AVAILABLE = _SA_AVAILABLE  # pgvector can be optional; bridge degrades to float[] SQL

if TYPE_CHECKING:
    from nodus.runtime.embedding import NodusRuntime
    from sqlalchemy.engine import Engine


_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS {table} (
    id TEXT PRIMARY KEY,
    embedding FLOAT[] NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{{}}'
)
"""

_UPSERT_SQL = """
INSERT INTO {table} (id, embedding, metadata)
VALUES (:id, :embedding, :metadata)
ON CONFLICT (id) DO UPDATE SET
    embedding = EXCLUDED.embedding,
    metadata = EXCLUDED.metadata
"""

_SEARCH_SQL = """
SELECT id, metadata FROM {table}
ORDER BY embedding <-> :query_vec
LIMIT :top_k
"""


class VectorBridge:
    """pgvector bridge for semantic search over embeddings.

    Uses pgvector's ``<->`` cosine distance operator when available;
    falls back to float[] storage for SQLite-based testing.

    Requires ``nodus-sdk[vector]`` (``pgvector>=0.2``, ``sqlalchemy>=2.0``).

    Usage::

        bridge = VectorBridge("postgresql://...")
        bridge.ensure_table()
        rt.attach_vector(bridge)
        # .nd: vector_upsert(id, [0.1, ...], {key: "val"})
        # .nd: vector_search([0.1, ...], 5)  → list of {id, metadata}
    """

    def __init__(
        self,
        engine_or_url: "str | Engine",
        *,
        table: str = "nodus_embeddings",
        dimensions: int = 1536,
    ) -> None:
        if not _SA_AVAILABLE:
            raise ImportError("sqlalchemy not installed. pip install nodus-sdk[vector]")
        from sqlalchemy import create_engine
        from sqlalchemy.engine import Engine as _Engine

        if isinstance(engine_or_url, _Engine):
            self._engine = engine_or_url
        else:
            self._engine = create_engine(str(engine_or_url))

        self._table = table
        self._dimensions = dimensions

    def ensure_table(self) -> None:
        """Create the embeddings table if it does not exist."""
        from sqlalchemy import text
        sql = _CREATE_TABLE_SQL.format(table=self._table)
        with self._engine.begin() as conn:
            conn.execute(text(sql))

    def upsert(self, id: str, vector: list[float], metadata: dict | None = None) -> None:
        """Insert or update an embedding."""
        from sqlalchemy import text
        sql = _UPSERT_SQL.format(table=self._table)
        with self._engine.begin() as conn:
            conn.execute(text(sql), {
                "id": id,
                "embedding": list(vector),
                "metadata": json.dumps(metadata or {}),
            })

    def search(
        self,
        vector: list[float],
        top_k: int = 10,
        *,
        metadata_filter: dict | None = None,
    ) -> list[dict]:
        """Return the top_k nearest neighbours. metadata_filter is not yet applied."""
        from sqlalchemy import text
        sql = _SEARCH_SQL.format(table=self._table)
        with self._engine.connect() as conn:
            rows = conn.execute(text(sql), {
                "query_vec": list(vector),
                "top_k": top_k,
            }).fetchall()
        results = []
        for row in rows:
            try:
                meta = json.loads(row[1]) if isinstance(row[1], str) else row[1]
            except (json.JSONDecodeError, TypeError):
                meta = {}
            results.append({"id": row[0], "metadata": meta})
        return results

    def delete(self, id: str) -> bool:
        """Delete an embedding by ID. Returns True if a row was deleted."""
        from sqlalchemy import text
        sql = f"DELETE FROM {self._table} WHERE id = :id"
        with self._engine.begin() as conn:
            result = conn.execute(text(sql), {"id": id})
            return result.rowcount > 0

    @property
    def engine(self) -> "Engine":
        return self._engine

    def register_host_functions(self, runtime: "NodusRuntime") -> None:
        """Register vector_upsert, vector_search, vector_delete on the runtime."""
        bridge = self

        def vector_upsert(id: Any, vec: Any, metadata: Any = None) -> None:
            if not isinstance(id, str) or not isinstance(vec, list):
                return
            meta = dict(metadata.fields) if hasattr(metadata, "fields") else (metadata or {})
            try:
                bridge.upsert(id, [float(x) for x in vec], meta)
            except Exception:
                pass

        def vector_search(vec: Any, top_k: Any = 10) -> list:
            if not isinstance(vec, list):
                return []
            k = int(top_k) if isinstance(top_k, (int, float)) else 10
            try:
                return bridge.search([float(x) for x in vec], k)
            except Exception:
                return []

        def vector_delete(id: Any) -> bool:
            if not isinstance(id, str):
                return False
            try:
                return bridge.delete(id)
            except Exception:
                return False

        runtime.register_function("vector_upsert", vector_upsert, arity=3)
        runtime.register_function("vector_search", vector_search, arity=2)
        runtime.register_function("vector_delete", vector_delete, arity=1)
