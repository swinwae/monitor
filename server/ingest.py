import json
import re
from datetime import datetime
from server.db import Host, Monitor, Tunnel, monitor_id
from server.schemas import ReportIn

DEFAULT_ERROR_PATTERN = r"ERROR|Exception|Traceback|panic|fatal|FATAL"


def count_errors(text: str, pattern: str = DEFAULT_ERROR_PATTERN) -> int:
    """统计日志文本中匹配错误模式的行数"""
    rx = re.compile(pattern)
    return sum(1 for line in text.splitlines() if rx.search(line))


def ingest_report(session, report: ReportIn, now: datetime) -> None:
    """将 agent 上报数据 upsert 进数据库

    - 更新或新建 Host,刷新 last_seen
    - 按 monitor_id 主键 upsert Monitor;保留已有记录的 is_watched 与用户设置的 display_name
    - 按 monitor_id 主键 upsert Tunnel
    """
    # upsert 主机
    host = session.get(Host, report.host.id)
    if host is None:
        host = Host(id=report.host.id, name=report.host.name, platform=report.host.platform)
    host.name = report.host.name
    host.platform = report.host.platform
    host.last_seen = now
    session.add(host)

    # upsert 监控进程
    for mi in report.monitors:
        mid = monitor_id(report.host.id, mi.type, mi.name)
        m = session.get(Monitor, mid)
        if m is None:
            m = Monitor(id=mid, host_id=report.host.id, type=mi.type, name=mi.name)
        m.status = mi.status
        m.started_at = mi.started_at
        m.restart_count = mi.restart_count
        m.last_exit_code = mi.last_exit_code
        m.enabled = mi.enabled
        m.meta = json.dumps(mi.meta, ensure_ascii=False)
        m.recent_logs = mi.recent_logs
        m.error_count = count_errors(mi.recent_logs)
        m.last_report_at = now
        # 仅当上报的 display_name 非 None 时才覆盖(保留用户改名)
        if mi.display_name is not None:
            m.display_name = mi.display_name
        session.add(m)

    # upsert 隧道
    for ti in report.tunnels:
        tid = monitor_id(report.host.id, "tunnel", ti.name)
        t = session.get(Tunnel, tid)
        if t is None:
            t = Tunnel(id=tid, frps_host_id=report.host.id, name=ti.name, proto=ti.proto)
        t.proto = ti.proto
        t.remote_port = ti.remote_port
        t.client_addr = ti.client_addr
        t.online = ti.online
        t.traffic_in = ti.traffic_in
        t.traffic_out = ti.traffic_out
        t.conn_count = ti.conn_count
        t.last_report_at = now
        session.add(t)
