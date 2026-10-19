from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlmodel import Session

from app import __version__
from app.core.db import get_session

router = APIRouter(tags=["system"])


@router.get("/health")
def health(request: Request, session: Session = Depends(get_session)) -> dict:
    settings = request.app.state.settings
    try:
        session.exec(text("SELECT 1"))
        db_ok = True
    except Exception:  # pragma: no cover - only when the DB is down
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "version": __version__,
        "mode": "full" if settings.queue_backend == "celery" else "lite",
        "database": settings.db_dialect,
        "db_ok": db_ok,
        "embeddings": request.app.state.mapping.embedder.describe(),
    }
