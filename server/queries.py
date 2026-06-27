import json
from datetime import datetime
from sqlmodel import select
from server.db import Host, Monitor, Tunnel
from server.status import effective_status, tunnel_online


def display_of(m: Monitor) -> str:
    return m.display_name or m.name


def _row(m: Monitor, now: datetime) -> dict:
    return {
        "id": m.id, "name": display_of(m), "raw_name": m.name, "type": m.type,
        "eff_status": effective_status(m, now), "restart_count": m.restart_count,
        "error_count": m.error_count, "last_report_at": m.last_report_at,
        "is_watched": m.is_watched,
    }


def overview(session, now: datetime) -> dict:
    hosts = session.exec(select(Host)).all()
    watched = session.exec(select(Monitor).where(Monitor.is_watched == True)).all()  # noqa: E712
    summary = {"total": 0, "up": 0, "down": 0, "unknown": 0, "errors": 0}
    host_rows = {h.id: {"id": h.id, "name": h.name, "platform": h.platform,
                        "last_seen": h.last_seen, "monitors": []} for h in hosts}
    for m in watched:
        st = effective_status(m, now)
        summary["total"] += 1
        summary[st] = summary.get(st, 0) + 1
        if m.error_count > 0:
            summary["errors"] += 1
        if m.host_id in host_rows:
            host_rows[m.host_id]["monitors"].append(_row(m, now))
    all_tunnels = session.exec(select(Tunnel)).all()
    online = sum(1 for t in all_tunnels if tunnel_online(t, now))
    return {"summary": summary, "hosts": list(host_rows.values()), "tunnels_online": online}


def host_all(session, host_id: str, now: datetime) -> list[dict]:
    ms = session.exec(select(Monitor).where(Monitor.host_id == host_id)).all()
    return [_row(m, now) for m in ms]


def monitor_detail(session, mid: str, now: datetime) -> dict | None:
    m = session.get(Monitor, mid)
    if m is None:
        return None
    return {
        "id": m.id, "host_id": m.host_id, "name": m.name, "display_name": m.display_name,
        "type": m.type, "eff_status": effective_status(m, now), "started_at": m.started_at,
        "restart_count": m.restart_count, "last_exit_code": m.last_exit_code,
        "enabled": m.enabled, "meta": json.loads(m.meta or "{}"),
        "recent_logs": m.recent_logs, "error_count": m.error_count,
        "is_watched": m.is_watched, "last_report_at": m.last_report_at,
    }


def tunnels(session, now: datetime) -> list[dict]:
    ts = session.exec(select(Tunnel)).all()
    return [{
        "name": t.name, "proto": t.proto, "remote_port": t.remote_port,
        "client_addr": t.client_addr, "online": tunnel_online(t, now),
        "traffic_in": t.traffic_in, "traffic_out": t.traffic_out,
        "conn_count": t.conn_count, "frps_host_id": t.frps_host_id,
    } for t in ts]
