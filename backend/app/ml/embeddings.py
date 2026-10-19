"""Lazy multilingual sentence-embedding model.

The model (paraphrase-multilingual-MiniLM-L12-v2) is loaded in a background thread
on first use and cached under storage/models/hf. Until it is ready, or if
sentence-transformers isn't installed or EMBEDDINGS_ENABLED=false, callers get
``None`` and the mapper falls back to BM25 + lexicon (and says so).
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)


class EmbeddingModel:
    def __init__(self, model_name: str, cache_dir: Path, enabled: bool = True) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.enabled = enabled
        self._model = None
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.status = "disabled" if not enabled else "not_loaded"
        self.error: str | None = None

    def _load(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # heavy import, deferred

            self.cache_dir.mkdir(parents=True, exist_ok=True)
            model = SentenceTransformer(self.model_name, cache_folder=str(self.cache_dir), device="cpu")
            with self._lock:
                self._model = model
                self.status = "ready"
            log.info("Embedding model ready: %s", self.model_name)
        except ImportError:
            self.status, self.error = "unavailable", "sentence-transformers is not installed"
        except Exception as exc:  # network down, disk full, ...
            self.status, self.error = "unavailable", f"{type(exc).__name__}: {exc}"
            log.warning("Embedding model unavailable: %s", self.error)

    def warm_up(self, block: bool = False) -> None:
        if not self.enabled or self.status in ("ready", "unavailable"):
            return
        with self._lock:
            if self._thread is None:
                self.status = "loading"
                self._thread = threading.Thread(target=self._load, name="embedding-warmup", daemon=True)
                self._thread.start()
        if block and self._thread is not None:
            self._thread.join()

    @property
    def ready(self) -> bool:
        return self._model is not None

    def encode(self, texts: list[str]) -> np.ndarray | None:
        if not self.ready:
            return None
        vecs = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vecs, dtype=np.float32)

    def describe(self) -> dict:
        return {"model": self.model_name, "status": self.status, "error": self.error}
