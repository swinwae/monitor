import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MONITOR_DB", str(tmp_path / "tp.db"))
    monkeypatch.setenv("MONITOR_TOKEN", "secret")
    import importlib, server.deps, server.api, server.main
    importlib.reload(server.deps); importlib.reload(server.api); importlib.reload(server.main)
    from server.main import app
    with TestClient(app) as c:
        c.post("/api/report", headers={"X-Monitor-Token": "secret"}, json={
            "host": {"id": "ecs", "name": "ECS", "platform": "linux"},
            "tunnels": [{"name": "web-terminal", "proto": "tcp", "remote_port": 7001,
                         "client_addr": "1.2.3.4", "online": True, "conn_count": 2}],
        })
        yield c

def test_tunnels_page(client):
    r = client.get("/tunnels")
    assert r.status_code == 200
    assert "web-terminal" in r.text and "7001" in r.text
