"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from app import __version__
from app.api import audit, auth, health, lexicon, qps
from app.core.config import Settings, get_settings
from app.core.db import make_engine, run_migrations
from app.services.users import seed_demo_users


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        run_migrations(settings.resolved_database_url)
        with Session(app.state.engine) as session:
            seed_demo_users(session, settings)
        yield
        app.state.engine.dispose()

    app = FastAPI(
        title="SkillSync Co-Pilot API",
        version=__version__,
        description=(
            "AI-assisted, assessor-calibrated, offline-first RPL assessment (SIH 2026 · PS 26242). "
            "The AI supports the assessor; it never replaces them."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = make_engine(settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(auth.users_router)
    app.include_router(audit.router)
    app.include_router(qps.router)
    app.include_router(lexicon.router)
    return app


app = create_app()
