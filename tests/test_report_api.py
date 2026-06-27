import os
os.environ["MONITOR_TOKEN"] = "secret"
os.environ["MONITOR_DB"] = ":memory:"

import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MONITOR_DB", str(tmp_path / "api.db"))
    monkeypatch.setenv("MONITOR_TOKEN", "secret")
    import importlib, server.deps, server.main
    importlib.reload(server.deps); importlib.reload(server.main)
    from server.main import app
    with TestClient(app) as c:
        yield c

PAYLOAD = {
    "host": {"id": "ecs", "name": "ECS", "platform": "linux"},
    "monitors": [{"type": "systemd", "name": "myblog", "status": "up"}],
}

def test_report_requires_token(client):
    assert client.post("/api/report", json=PAYLOAD).status_code == 401

def test_report_ok(client):
    r = client.post("/api/report", json=PAYLOAD, headers={"X-Monitor-Token": "secret"})
    assert r.status_code == 200 and r.json() == {"ok": True}

def test_report_wrong_token(client):
    r = client.post("/api/report", json=PAYLOAD, headers={"X-Monitor-Token": "nope"})
    assert r.status_code == 401
