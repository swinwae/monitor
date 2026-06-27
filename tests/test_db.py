from sqlmodel import Session, select
from server.db import get_engine, init_db, Host, Monitor, monitor_id


def test_monitor_id_stable():
    a = monitor_id("ecs", "systemd", "myblog")
    b = monitor_id("ecs", "systemd", "myblog")
    assert a == b
    assert a != monitor_id("ecs", "systemd", "myurls")


def test_init_and_insert(tmp_path):
    engine = get_engine(str(tmp_path / "t.db"))
    init_db(engine)
    with Session(engine) as s:
        s.add(Host(id="ecs", name="ECS", platform="linux"))
        s.add(Monitor(id="m1", host_id="ecs", type="systemd", name="myblog",
                      status="up", restart_count=0, enabled=True,
                      meta="{}", recent_logs="", error_count=0, is_watched=True))
        s.commit()
    with Session(engine) as s:
        hosts = s.exec(select(Host)).all()
        assert len(hosts) == 1 and hosts[0].id == "ecs"
