"""Pre-download the multilingual embedding model used by the QP mapper re-rank.

The model (sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2, ~470 MB)
is cached under storage/models/hf. Without it the mapper still works with BM25 +
lexicon only, and says so in the UI.

Usage:  python scripts/download_models.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.ml.embeddings import EmbeddingModel  # noqa: E402


def main() -> int:
    settings = get_settings()
    model = EmbeddingModel(settings.embedding_model, settings.storage_path / "models" / "hf", enabled=True)
    t0 = time.time()
    print(f"Downloading / loading {settings.embedding_model} into {model.cache_dir} ...")
    model.warm_up(block=True)
    print(f"status={model.status} error={model.error} ({time.time() - t0:.1f}s)")
    if not model.ready:
        return 1
    vec = model.encode(["argon ka kaam", "GTAW (141) TIG welding"])
    print(f"embedding dim={vec.shape[1]}, cos(argon ka kaam, GTAW TIG)={float(vec[0] @ vec[1]):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
