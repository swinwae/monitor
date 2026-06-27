import hashlib
from datetime import datetime
from sqlmodel import SQLModel, Field, create_engine


def monitor_id(host_id: str, type: str, name: str) -> str:
    raw = f"{host_id}|{type}|{name}".encode()
    return hashlib.sha1(raw).hexdigest()


class Host(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    platform: str
    last_seen: datetime | None = None


class Monitor(SQLModel, table=True):
    id: str = Field(primary_key=True)
    host_id: str = Field(index=True)
    type: str
    name: str
    display_name: str | None = None
    status: str = "unknown"
    started_at: str | None = None
    restart_count: int = 0
    last_exit_code: int | None = None
    enabled: bool = False
    meta: str = "{}"            # JSON 字符串
    recent_logs: str = ""
    error_count: int = 0
    is_watched: bool = False
    last_report_at: datetime | None = None


class Tunnel(SQLModel, table=True):
    id: str = Field(primary_key=True)
    frps_host_id: str = Field(index=True)
    name: str
    proto: str
    remote_port: int | None = None
    client_addr: str | None = None
    client_host_id: str | None = None
    online: bool = False
    traffic_in: int = 0
    traffic_out: int = 0
    conn_count: int = 0
    last_report_at: datetime | None = None


def get_engine(db_path: str):
    return create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})


def init_db(engine) -> None:
    SQLModel.metadata.create_all(engine)
