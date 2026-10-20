"""Celery worker for Docker full mode (QUEUE_BACKEND=celery).

Run:  celery -A app.worker worker --loglevel=info
Lite mode never imports this module: it uses FastAPI BackgroundTasks instead.
"""

from __future__ import annotations

from functools import lru_cache

from celery import Celery

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery("skillsync", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_acks_late = True
celery_app.conf.worker_prefetch_multiplier = 1


@lru_cache
def _deps():
    from app.core.db import make_engine
    from app.ml.shadow_rater import load_rater
    from app.services.storage import make_storage

    return make_engine(settings), make_storage(settings), load_rater()


@celery_app.task(
    name="skillsync.analyse_evidence", autoretry_for=(Exception,), retry_backoff=True, max_retries=3
)
def analyse_evidence_task(evidence_id: int) -> str:
    from app.services.ai_service import analyse_evidence

    engine, storage, rater = _deps()
    analyse_evidence(engine, storage, rater, evidence_id)
    return f"analysed evidence {evidence_id}"
