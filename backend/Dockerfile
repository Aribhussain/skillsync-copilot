# SkillSync Co-Pilot API (Docker full mode). Build context: the repo root.
# No torch / sentence-transformers here: the embedding re-rank stays a lite-mode
# option (EMBEDDINGS_ENABLED=false in compose), BM25 + lexicon still runs.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app/backend

COPY backend/requirements.txt backend/requirements-full.txt ./
RUN pip install -r requirements.txt -r requirements-full.txt

COPY backend/alembic.ini backend/pyproject.toml ./
COPY backend/alembic ./alembic
COPY backend/app ./app
COPY data /app/data
COPY scripts /app/scripts
COPY ml/*.py /app/ml/

RUN useradd --create-home --uid 10001 skillsync \
    && mkdir -p /app/storage /app/ml/models \
    && chown -R skillsync:skillsync /app/storage /app/ml/models
USER skillsync

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
