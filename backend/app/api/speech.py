"""Speech adapter configuration.

Default speech recognition runs in the browser (Web Speech API, hi-IN / en-IN), with typed
input and icon cards always available. A Bhashini ASR adapter is *scaffolded*: it is
offered to the client only when BHASHINI_API_KEY is set, and the server-side transcription
call is NOT implemented in this prototype, because we have no Bhashini (ULCA) credentials
to build and test it against. The endpoint says so explicitly instead of failing silently.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/speech", tags=["speech"])


@router.get("/config")
def speech_config(request: Request) -> dict:
    settings = request.app.state.settings
    return {
        "default": "web-speech",
        "languages": ["hi-IN", "en-IN"],
        "bhashini": {
            "configured": bool(settings.bhashini_api_key),
            "implemented": False,
            "note": "Scaffold only: needs Bhashini ULCA credentials to implement and test.",
        },
        "fallbacks": ["typed", "icon-cards"],
    }


@router.post("/transcribe", status_code=501)
def transcribe(request: Request, _: User = Depends(get_current_user)) -> dict:
    settings = request.app.state.settings
    if not settings.bhashini_api_key:
        raise HTTPException(404, "Bhashini adapter is not enabled (BHASHINI_API_KEY is empty)")
    raise HTTPException(
        501,
        "Bhashini transcription is scaffolded but not implemented in this prototype. "
        "Use browser speech, typing or icon cards.",
    )
