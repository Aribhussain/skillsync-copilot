"""Background job dispatch, chosen by QUEUE_BACKEND:
background  FastAPI BackgroundTasks in the API process (lite mode, default)
celery      a Celery task on Redis, run by the `worker` container (Docker full mode)
"""

from __future__ import annotations

from fastapi import BackgroundTasks, Request

from app.services.ai_service import analyse_evidence


def dispatch_evidence_analysis(request: Request, background: BackgroundTasks, evidence_id: int) -> str:
    st = request.app.state
    if st.settings.queue_backend == "celery":
        from app.worker import analyse_evidence_task  # full-mode dependency

        analyse_evidence_task.delay(evidence_id)
        return "celery"
    background.add_task(analyse_evidence, st.engine, st.storage, st.rater, evidence_id)
    return "background"
