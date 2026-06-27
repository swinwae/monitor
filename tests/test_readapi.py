import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MONITOR_DB", str(tmp_path / "r.db"))
    monkeypatch.setenv("MONITOR_TOKEN", "secret")
    import importlib, server.deps, server.api, server.main
    importlib.reload(server.deps); importlib.reload(server.api); importlib.reload(server.main)
    from server.main import app
    with TestClient(app) as c:
        c.post("/api/report", headers={"X-Monitor-Token": "secret"}, json={
            "host": {"id": "ecs", "name": "ECS", "platform": "linux"},
            "monitors": [{"type": "systemd", "name": "myblog", "status": "up"}],
        })
        yield c

def _mid(c):
    return c.get("/api/hosts/ecs/all").json()[0]["id"]

def test_overview(client):
    ov = client.get("/api/overview").json()
    assert ov["summary"]["total"] == 0  # 默认未关注

def test_watch_then_overview(client):
    mid = _mid(client)
    r = client.post(f"/api/monitors/{mid}/watch", json={"watched": True})
    assert r.json()["is_watched"] is True
    assert client.get("/api/overview").json()["summary"]["total"] == 1

def test_rename(client):
    mid = _mid(client)
    client.patch(f"/api/monitors/{mid}", json={"display_name": "我的博客"})
    assert client.get(f"/api/monitors/{mid}").json()["display_name"] == "我的博客"

def test_detail_404(client):
    assert client.get("/api/monitors/nope").status_code == 404
