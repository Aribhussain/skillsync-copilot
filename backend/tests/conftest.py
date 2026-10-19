import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture()
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        storage_dir=str(tmp_path / "storage"),
        embeddings_enabled=False,
    )


@pytest.fixture()
def client(settings):
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


DEMO_PASSWORDS = {"worker": "worker123", "assessor": "assessor123", "qa": "qa123", "admin": "admin123"}


def password_for(username: str) -> str:
    return next(v for k, v in DEMO_PASSWORDS.items() if username.startswith(k))


@pytest.fixture()
def auth(client):
    """auth("assessor1") -> Authorization header dict."""
    cache: dict[str, dict] = {}

    def _headers(username: str) -> dict:
        if username not in cache:
            r = client.post("/auth/login", json={"username": username, "password": password_for(username)})
            assert r.status_code == 200, r.text
            cache[username] = {"Authorization": f"Bearer {r.json()['access_token']}"}
        return cache[username]

    return _headers
