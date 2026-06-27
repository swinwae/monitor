from datetime import datetime, timedelta
from server.db import Monitor, Tunnel
from server.status import effective_status, tunnel_online, STALE_SECONDS

NOW = datetime(2026, 6, 27, 12, 0, 0)

def _m(status, secs_ago):
    return Monitor(id="x", host_id="h", type="systemd", name="n", status=status,
                   last_report_at=NOW - timedelta(seconds=secs_ago),
                   restart_count=0, enabled=True, meta="{}", recent_logs="", error_count=0)

def test_fresh_up():
    assert effective_status(_m("up", 10), NOW) == "up"

def test_stale_becomes_unknown():
    assert effective_status(_m("up", STALE_SECONDS + 1), NOW) == "unknown"

def test_never_reported_unknown():
    m = _m("up", 10); m.last_report_at = None
    assert effective_status(m, NOW) == "unknown"

def test_down_stays_down_when_fresh():
    assert effective_status(_m("down", 5), NOW) == "down"

def test_tunnel_stale_offline():
    t = Tunnel(id="t", frps_host_id="h", name="n", proto="tcp", online=True,
               last_report_at=NOW - __import__("datetime").timedelta(seconds=STALE_SECONDS + 1))
    assert tunnel_online(t, NOW) is False
