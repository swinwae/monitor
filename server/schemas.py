from pydantic import BaseModel, Field


class HostIn(BaseModel):
    """主机信息入站模型"""
    id: str
    name: str
    platform: str


class MonitorIn(BaseModel):
    """监控进程入站模型"""
    type: str
    name: str
    display_name: str | None = None
    status: str
    started_at: str | None = None
    restart_count: int = 0
    last_exit_code: int | None = None
    enabled: bool = False
    meta: dict = Field(default_factory=dict)
    recent_logs: str = ""


class TunnelIn(BaseModel):
    """隧道入站模型"""
    name: str
    proto: str
    remote_port: int | None = None
    client_addr: str | None = None
    online: bool = False
    traffic_in: int = 0
    traffic_out: int = 0
    conn_count: int = 0


class ReportIn(BaseModel):
    """代理上报数据入站模型"""
    host: HostIn
    monitors: list[MonitorIn] = Field(default_factory=list)
    tunnels: list[TunnelIn] = Field(default_factory=list)
