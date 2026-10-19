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
