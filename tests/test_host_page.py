import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MONITOR_DB", str(tmp_path / "h.db"))
    monkeypatch.setenv("MONITOR_TOKEN", "secret")
    import importlib, server.deps, server.api, server.main
    importlib.reload(server.deps); importlib.reload(server.api); importlib.reload(server.main)
    from server.main import app
    with TestClient(app) as c:
        c.post("/api/report", headers={"X-Monitor-Token": "secret"}, json={
            "host": {"id": "ecs", "name": "ECS", "platform": "linux"},
            "monitors": [{"type": "systemd", "name": "myblog", "status": "up"},
                         {"type": "systemd", "name": "redis", "status": "up"}],
        })
        yield c

def test_host_page_lists_all(client):
    r = client.get("/hosts/ecs")
    assert r.status_code == 200
    assert "myblog" in r.text and "redis" in r.text
    assert "关注" in r.text
