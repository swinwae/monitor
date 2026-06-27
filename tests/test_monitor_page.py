import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MONITOR_DB", str(tmp_path / "m.db"))
    monkeypatch.setenv("MONITOR_TOKEN", "secret")
    import importlib, server.deps, server.api, server.main
    importlib.reload(server.deps); importlib.reload(server.api); importlib.reload(server.main)
    from server.main import app
    with TestClient(app) as c:
        c.post("/api/report", headers={"X-Monitor-Token": "secret"}, json={
            "host": {"id": "ecs", "name": "ECS", "platform": "linux"},
            "monitors": [{"type": "systemd", "name": "myblog", "status": "up",
                          "meta": {"cmd": "java -jar x.jar"},
                          "recent_logs": "started ok\nERROR boom"}],
        })
        yield c

def _mid(c):
    return c.get("/api/hosts/ecs/all").json()[0]["id"]

def test_monitor_page(client):
    r = client.get(f"/monitors/{_mid(client)}")
    assert r.status_code == 200
    assert "java -jar x.jar" in r.text
    assert "ERROR boom" in r.text

def test_monitor_page_404(client):
    assert client.get("/monitors/nope").status_code == 404
