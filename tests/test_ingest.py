import json
from datetime import datetime
from sqlmodel import Session, select
from server.db import get_engine, init_db, Monitor, Host, Tunnel
from server.schemas import ReportIn
from server.ingest import ingest_report, count_errors

T0 = datetime(2026, 6, 27, 12, 0, 0)

def _engine(tmp_path):
    e = get_engine(str(tmp_path / "t.db")); init_db(e); return e

def test_count_errors():
    assert count_errors("all good\nline2") == 0
    assert count_errors("ERROR boom\nTraceback (most recent)\nok") == 2

def test_ingest_inserts(tmp_path):
    e = _engine(tmp_path)
    report = ReportIn.model_validate({
        "host": {"id": "ecs", "name": "ECS", "platform": "linux"},
        "monitors": [{"type": "systemd", "name": "myblog", "status": "up",
                      "restart_count": 3, "enabled": True,
                      "meta": {"cmd": "java -jar x.jar"},
                      "recent_logs": "ERROR oops\nok"}],
        "tunnels": [{"name": "web", "proto": "tcp", "remote_port": 7001, "online": True}],
    })
    with Session(e) as s:
        ingest_report(s, report, T0); s.commit()
    with Session(e) as s:
        m = s.exec(select(Monitor)).one()
        assert m.host_id == "ecs" and m.error_count == 1
        assert json.loads(m.meta)["cmd"] == "java -jar x.jar"
        assert m.last_report_at == T0
        h = s.exec(select(Host)).one(); assert h.last_seen == T0
        t = s.exec(select(Tunnel)).one(); assert t.online is True

def test_ingest_preserves_watch_and_displayname(tmp_path):
    e = _engine(tmp_path)
    base = {"host": {"id": "ecs", "name": "ECS", "platform": "linux"},
            "monitors": [{"type": "systemd", "name": "myblog", "status": "up"}]}
    with Session(e) as s:
        ingest_report(s, ReportIn.model_validate(base), T0)
        m = s.exec(select(Monitor)).one()
        m.is_watched = True; m.display_name = "我的博客"
        s.add(m); s.commit()
    # 二次上报不带 display_name,且 is_watched 不应被重置
    with Session(e) as s:
        ingest_report(s, ReportIn.model_validate(base), T0); s.commit()
        m = s.exec(select(Monitor)).one()
        assert m.is_watched is True and m.display_name == "我的博客"
