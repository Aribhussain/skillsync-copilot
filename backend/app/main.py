"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from app import __version__
from app.api import (
    assessments,
    audit,
    auth,
    calibration,
    credentials,
    declarations,
    evidence,
    health,
    lexicon,
    packs,
    profile,
    qps,
    scoring,
    speech,
    studies,
)
from app.core.config import Settings, get_settings
from app.core.db import make_engine, run_migrations
from app.ml.shadow_rater import load_rater
from app.services.mapping_service import MappingService
from app.services.storage import LocalStorage
from app.services.users import seed_demo_users


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        run_migrations(settings.resolved_database_url)
        with Session(app.state.engine) as session:
            seed_demo_users(session, settings)
        app.state.mapping.warm_up()  # loads the embedding model in a background thread
        app.state.rater = load_rater()  # demo shadow rater (trains on first run if missing)
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
    app.state.mapping = MappingService(settings, app.state.engine)
    app.state.storage = LocalStorage(settings.storage_path)

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
    app.include_router(declarations.router)
    app.include_router(packs.router)
    app.include_router(assessments.router)
    app.include_router(assessments.assessor_router)
    app.include_router(speech.router)
    app.include_router(evidence.router)
    app.include_router(scoring.router)
    app.include_router(calibration.router)
    app.include_router(profile.router)
    app.include_router(credentials.router)
    app.include_router(studies.router)
    return app


app = create_app()
