def test_health_reports_ok_and_lite_mode(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["mode"] == "lite"
    assert body["database"] == "sqlite"
