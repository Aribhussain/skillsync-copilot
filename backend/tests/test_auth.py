import pytest


def login(client, username, password):
    return client.post("/auth/login", json={"username": username, "password": password})


def auth_headers(client, username, password=None):
    password = (
        password
        or {
            "worker": "worker123",
            "assessor": "assessor123",
            "qa": "qa123",
            "admin": "admin123",
        }[next(k for k in ("worker", "assessor", "qa", "admin") if username.startswith(k))]
    )
    token = login(client, username, password).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_demo_users_are_seeded_and_can_log_in(client):
    accounts = client.get("/auth/demo-accounts").json()
    names = {a["username"] for a in accounts}
    assert {"worker1", "worker2", "assessor1", "assessor2", "assessor3", "qa1", "admin"} <= names
    for a in accounts:
        r = login(client, a["username"], a["password"])
        assert r.status_code == 200, a["username"]
        assert r.json()["user"]["role"] == a["role"]


def test_wrong_password_is_rejected(client):
    assert login(client, "worker1", "nope").status_code == 401


def test_me_requires_token(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401
    r = client.get("/auth/me", headers=auth_headers(client, "assessor1"))
    assert r.status_code == 200 and r.json()["username"] == "assessor1"


@pytest.mark.parametrize(
    ("username", "expected"),
    [("worker1", 403), ("assessor1", 403), ("qa1", 200), ("admin", 200)],
)
def test_rbac_on_user_listing(client, username, expected):
    r = client.get("/users", headers=auth_headers(client, username))
    assert r.status_code == expected


def test_oauth2_form_token_endpoint(client):
    r = client.post("/auth/token", data={"username": "qa1", "password": "qa123"})
    assert r.status_code == 200 and r.json()["token_type"] == "bearer"


def test_demo_accounts_hidden_in_production(settings):
    from fastapi.testclient import TestClient

    from app.main import create_app

    settings.app_env = "production"
    with TestClient(create_app(settings)) as c:
        assert c.get("/auth/demo-accounts").json() == []
