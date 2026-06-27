from datetime import datetime
from server.db import Monitor, Tunnel

STALE_SECONDS = 90


def _is_stale(last_report_at, now: datetime) -> bool:
    if last_report_at is None:
        return True
    return (now - last_report_at).total_seconds() > STALE_SECONDS


def effective_status(m: Monitor, now: datetime) -> str:
    if _is_stale(m.last_report_at, now):
        return "unknown"
    return m.status


def tunnel_online(t: Tunnel, now: datetime) -> bool:
    if _is_stale(t.last_report_at, now):
        return False
    return t.online
