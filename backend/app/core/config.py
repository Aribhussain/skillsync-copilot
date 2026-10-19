"""Application settings, loaded from the repo-root `.env` (or `backend/.env`)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
DATA_DIR = REPO_ROOT / "data"
ML_DIR = REPO_ROOT / "ml"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    database_url: str = "sqlite:///./storage/skillsync.db"
    storage_dir: str = "./storage"
    jwt_secret: str = "dev-only-secret-change-me-0123456789abcdef"
    jwt_expire_minutes: int = 720
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    public_app_url: str = "http://localhost:5173"

    demo_password_worker: str = "worker123"
    demo_password_assessor: str = "assessor123"
    demo_password_qa: str = "qa123"
    demo_password_admin: str = "admin123"

    embeddings_enabled: bool = True
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    ai_gap_threshold: int = 2
    phash_hamming_threshold: int = 10

    bhashini_api_key: str = ""
    bhashini_user_id: str = ""

    storage_backend: str = "local"  # local | s3
    queue_backend: str = "background"  # background | celery
    s3_endpoint: str = "http://minio:9000"
    s3_access_key: str = "skillsync"
    s3_secret_key: str = "skillsync-dev-secret"
    s3_bucket: str = "evidence"
    redis_url: str = "redis://redis:6379/0"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def resolved_database_url(self) -> str:
        """Relative SQLite paths are resolved against the repo root so the app
        behaves the same whether it is started from `backend/` or the root."""
        url = self.database_url
        prefix = "sqlite:///"
        if url.startswith(prefix) and not url.startswith("sqlite:////"):
            path = url[len(prefix) :]
            if path and path != ":memory:" and not Path(path).is_absolute():
                abs_path = (REPO_ROOT / path).resolve()
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                return f"{prefix}{abs_path.as_posix()}"
        return url

    @property
    def storage_path(self) -> Path:
        p = Path(self.storage_dir)
        if not p.is_absolute():
            p = (REPO_ROOT / p).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def db_dialect(self) -> str:
        return self.resolved_database_url.split(":", 1)[0].split("+", 1)[0]


@lru_cache
def get_settings() -> Settings:
    return Settings()
