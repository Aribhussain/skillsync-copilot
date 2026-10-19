"""Owns the QPMapper instance, the embedding model and the persisted QP vectors.

The mapper is rebuilt when the lexicon version changes (assessor additions). QP
embeddings are computed once per model, stored in `qp_embeddings` and loaded into a
NumpyVectorIndex.
"""

from __future__ import annotations

import threading
from typing import Any

from sqlalchemy import Engine
from sqlmodel import Session, select

from app.core.config import Settings
from app.core.security import sha256_hex
from app.ml.embeddings import EmbeddingModel
from app.models.declaration import QPEmbedding
from app.services.lexicon import all_entries, lexicon_version
from app.services.mapping import QPMapper, qp_embedding_text
from app.services.qp_store import get_corpus


class MappingService:
    def __init__(self, settings: Settings, engine: Engine) -> None:
        self.settings = settings
        self.engine = engine
        self.embedder = EmbeddingModel(
            settings.embedding_model,
            settings.storage_path / "models" / "hf",
            enabled=settings.embeddings_enabled,
        )
        self._mapper: QPMapper | None = None
        self._lock = threading.Lock()

    def warm_up(self) -> None:
        self.embedder.warm_up(block=False)

    def _qp_vectors(self, session: Session) -> dict[str, list[float]]:
        corpus = get_corpus()
        model = self.settings.embedding_model
        stored = {row.ref: row for row in session.exec(select(QPEmbedding).where(QPEmbedding.model == model))}
        vectors: dict[str, list[float]] = {}
        missing: list[tuple[str, str, str]] = []
        for qp_id, qp in corpus.items():
            text = qp_embedding_text(qp)
            digest = sha256_hex(text)
            row = stored.get(f"qp:{qp_id}")
            if row and row.text_sha256 == digest:
                vectors[qp_id] = row.vector
            else:
                missing.append((qp_id, text, digest))
        if missing:
            encoded = self.embedder.encode([m[1] for m in missing])
            if encoded is None:
                return vectors
            for (qp_id, _, digest), vec in zip(missing, encoded, strict=True):
                ref = f"qp:{qp_id}"
                row = stored.get(ref) or QPEmbedding(ref=ref, model=model, text_sha256=digest, vector=[])
                row.text_sha256 = digest
                row.vector = [round(float(x), 6) for x in vec]
                session.add(row)
                vectors[qp_id] = row.vector
            session.commit()
        return vectors

    def get_mapper(self, session: Session) -> QPMapper:
        version = lexicon_version(session)
        with self._lock:
            mapper = self._mapper
            if mapper is None or mapper.lexicon_version != version:
                mapper = QPMapper(get_corpus(), all_entries(session), version)
                self._mapper = mapper
            if mapper.vector_index is None and self.embedder.ready:
                mapper.attach_embeddings(self.embedder, self._qp_vectors(session))
        return mapper

    def map(self, session: Session, narrative: str) -> dict[str, Any]:
        result = self.get_mapper(session).map(narrative)
        result["embedding"] = self.embedder.describe()
        if result["engine"] != "hybrid":
            result["embedding_note"] = {
                "disabled": "Embedding re-rank disabled (EMBEDDINGS_ENABLED=false): BM25 + lexicon only.",
                "not_loaded": "Embedding model not loaded yet: BM25 + lexicon only.",
                "loading": "Embedding model is loading: BM25 + lexicon only for now.",
                "unavailable": "Embedding model unavailable: BM25 + lexicon only.",
            }.get(self.embedder.status, "BM25 + lexicon only.")
        return result
