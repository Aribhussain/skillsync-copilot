"""Vector search behind a small interface.

Lite mode uses NumpyVectorIndex: embeddings live in the database as JSON and are
loaded into an in-memory matrix (the corpus is tiny). Docker full mode can swap in
a pgvector-backed implementation without touching the mapper.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np


class VectorIndex(Protocol):
    def add(self, ref: str, vector: list[float] | np.ndarray) -> None: ...

    def search(self, query: np.ndarray, k: int = 10) -> list[tuple[str, float]]: ...

    def similarity(self, query: np.ndarray) -> dict[str, float]: ...

    def __len__(self) -> int: ...


class NumpyVectorIndex:
    """Cosine similarity over an in-memory matrix of L2-normalised rows."""

    def __init__(self) -> None:
        self._refs: list[str] = []
        self._rows: list[np.ndarray] = []
        self._matrix: np.ndarray | None = None

    @staticmethod
    def _norm(v: np.ndarray) -> np.ndarray:
        v = np.asarray(v, dtype=np.float32)
        n = float(np.linalg.norm(v))
        return v / n if n > 0 else v

    def add(self, ref: str, vector) -> None:
        self._refs.append(ref)
        self._rows.append(self._norm(np.asarray(vector, dtype=np.float32)))
        self._matrix = None

    def _mat(self) -> np.ndarray:
        if self._matrix is None:
            self._matrix = np.vstack(self._rows) if self._rows else np.zeros((0, 1), np.float32)
        return self._matrix

    def similarity(self, query) -> dict[str, float]:
        if not self._refs:
            return {}
        sims = self._mat() @ self._norm(query)
        return {r: float(s) for r, s in zip(self._refs, sims, strict=True)}

    def search(self, query, k: int = 10) -> list[tuple[str, float]]:
        sims = self.similarity(query)
        return sorted(sims.items(), key=lambda kv: kv[1], reverse=True)[:k]

    def __len__(self) -> int:
        return len(self._refs)


class PgVectorIndex:
    """pgvector-backed index for Docker full mode (PostgreSQL 16 + the `vector` extension).
    Plain SQL with text-cast vectors, so no extra driver package is needed."""

    def __init__(self, engine, dim: int, table: str = "qp_vectors") -> None:
        from sqlalchemy import text

        self.engine, self.dim, self.table, self._text = engine, dim, table, text
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(
                text(
                    f"CREATE TABLE IF NOT EXISTS {table} "
                    f"(ref varchar(96) PRIMARY KEY, embedding vector({dim}))"
                )
            )

    @staticmethod
    def _lit(v) -> str:
        n = NumpyVectorIndex._norm(np.asarray(v, dtype=np.float32))
        return "[" + ",".join(f"{x:.7f}" for x in n) + "]"

    def add(self, ref: str, vector) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                self._text(
                    f"INSERT INTO {self.table} (ref, embedding) VALUES (:r, CAST(:v AS vector)) "
                    "ON CONFLICT (ref) DO UPDATE SET embedding = EXCLUDED.embedding"
                ),
                {"r": ref, "v": self._lit(vector)},
            )

    def similarity(self, query) -> dict[str, float]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                self._text(f"SELECT ref, 1 - (embedding <=> CAST(:q AS vector)) FROM {self.table}"),
                {"q": self._lit(query)},
            ).all()
        return {r: float(s) for r, s in rows}

    def search(self, query, k: int = 10) -> list[tuple[str, float]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                self._text(
                    f"SELECT ref, 1 - (embedding <=> CAST(:q AS vector)) AS s FROM {self.table} "
                    "ORDER BY embedding <=> CAST(:q AS vector) LIMIT :k"
                ),
                {"q": self._lit(query), "k": k},
            ).all()
        return [(r, float(s)) for r, s in rows]

    def __len__(self) -> int:
        with self.engine.connect() as conn:
            return int(conn.execute(self._text(f"SELECT count(*) FROM {self.table}")).scalar_one())
