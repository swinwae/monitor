from datetime import datetime
from sqlmodel import Session
from server.db import get_engine, init_db
from server.schemas import ReportIn
from server.ingest import ingest_report
from server.queries import overview, host_all, monitor_detail, tunnels
from server.db import monitor_id, Monitor

NOW = datetime(2026, 6, 27, 12, 0, 0)

def _seed(tmp_path):
    e = get_engine(str(tmp_path / "q.db")); init_db(e)
    rep = ReportIn.model_validate({
        "host": {"id": "ecs", "name": "ECS", "platform": "linux"},
        "monitors": [
            {"type": "systemd", "name": "myblog", "status": "up", "recent_logs": "ERROR x"},
            {"type": "systemd", "name": "myurls", "status": "down"},
        ],
        "tunnels": [{"name": "web", "proto": "tcp", "remote_port": 7001, "online": True}],
    })
    with Session(e) as s:
        ingest_report(s, rep, NOW)
        # 只关注 myblog
        mid = monitor_id("ecs", "systemd", "myblog")
        m = s.get(Monitor, mid); m.is_watched = True; s.add(m); s.commit()
    return e

def test_overview_only_watched(tmp_path):
    e = _seed(tmp_path)
    with Session(e) as s:
        ov = overview(s, NOW)
    assert ov["summary"]["total"] == 1      # 只统计关注的
    assert ov["summary"]["up"] == 1
    assert ov["summary"]["errors"] == 1
    assert ov["tunnels_online"] == 1
    assert ov["hosts"][0]["monitors"][0]["type"] == "systemd"

def test_host_all_includes_unwatched(tmp_path):
    e = _seed(tmp_path)
    with Session(e) as s:
        rows = host_all(s, "ecs", NOW)
    assert len(rows) == 2
    assert {r["is_watched"] for r in rows} == {True, False}

def test_monitor_detail(tmp_path):
    e = _seed(tmp_path)
    mid = monitor_id("ecs", "systemd", "myblog")
    with Session(e) as s:
        d = monitor_detail(s, mid, NOW)
    assert d["name"] == "myblog" and d["eff_status"] == "up"

def test_tunnels(tmp_path):
    e = _seed(tmp_path)
    with Session(e) as s:
        ts = tunnels(s, NOW)
    assert ts[0]["name"] == "web" and ts[0]["online"] is True
