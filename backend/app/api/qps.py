from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.qp_store import get_corpus, get_qp, qp_summary

router = APIRouter(prefix="/qps", tags=["qualification packs"])


@router.get("")
def list_qps() -> list[dict]:
    return [qp_summary(q) for q in get_corpus().values()]


@router.get("/{qp_id}")
def read_qp(qp_id: str) -> dict:
    qp = get_qp(qp_id)
    if not qp:
        raise HTTPException(404, "Unknown qualification pack")
    return qp
