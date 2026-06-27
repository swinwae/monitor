# Monitor 中心 Server 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 monitor 的中心服务:接收各机器 agent 的上报、存进 SQLite、并用中文 Web 面板展示全局概览、对象明细与 frp 隧道拓扑。

**Architecture:** 单进程 FastAPI 应用。agent 通过 `POST /api/report` 上报 `{host, monitors[], tunnels[]}`,server upsert 进 SQLite(SQLModel)。对象的"失联(unknown)"状态在读取时按 `last_report_at` 动态派生,无需后台任务。前端用 Jinja2 服务端模板 + Tailwind CDN + 少量原生 JS,定时轮询刷新。

**Tech Stack:** Python 3.11+、FastAPI、SQLModel、uvicorn、Jinja2、pytest + httpx TestClient。

## Global Constraints

- Python 版本 ≥ 3.11(使用标准库 `tomllib`)。
- 依赖:`fastapi`、`sqlmodel`、`uvicorn[standard]`、`jinja2`、`python-multipart`;测试 `pytest`、`httpx`。
- 所有面板可见文字、注释、commit message 用中文;变量/函数/类/文件名、JSON key、配置 key 用英文。
- 单进程;数据库为单个 SQLite 文件,路径由环境变量 `MONITOR_DB`(默认 `monitor.db`)指定。
- 上报鉴权:请求头 `X-Monitor-Token` 必须等于环境变量 `MONITOR_TOKEN`;未配置 token 时拒绝所有上报。
- 失联阈值:对象 `last_report_at` 距当前超过 90 秒,有效状态派生为 `unknown`。
- 错误正则(默认):`ERROR|Exception|Traceback|panic|fatal|FATAL`,用于计算 `error_count`。
- 所有涉及"当前时间"的函数显式接收 `now: datetime` 参数,便于测试,不在业务函数内部直接调 `datetime.now()`。

---

### Task 1: 项目脚手架与可启动的 FastAPI app

**Files:**
- Create: `server/__init__.py`
- Create: `server/main.py`
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `tests/__init__.py`
- Test: `tests/test_health.py`

**Interfaces:**
- Produces: `server.main.app`(FastAPI 实例);`GET /api/health` 返回 `{"status": "ok"}`。

- [ ] **Step 1: 写依赖文件**

`requirements.txt`:
```
fastapi
sqlmodel
uvicorn[standard]
jinja2
python-multipart
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest
httpx
```

- [ ] **Step 2: 写失败的测试**

`tests/test_health.py`:
```python
from fastapi.testclient import TestClient
from server.main import app

client = TestClient(app)

def test_health_ok():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 3: 运行测试确认失败**

Run: `pip install -r requirements-dev.txt && python -m pytest tests/test_health.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'server.main'`

- [ ] **Step 4: 写最小实现**

`server/__init__.py`:(空文件)

`tests/__init__.py`:(空文件)

`server/main.py`:
```python
from fastapi import FastAPI

app = FastAPI(title="Monitor")


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add requirements.txt requirements-dev.txt server/ tests/
git commit -m "feat: 搭建 server 脚手架与健康检查接口"
```

---

### Task 2: 数据库模型与建表

**Files:**
- Create: `server/db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces:
  - SQLModel 表类 `Host(id:str, name:str, platform:str, last_seen:datetime|None)`
  - `Monitor(id:str, host_id:str, type:str, name:str, display_name:str|None, status:str, started_at:str|None, restart_count:int, last_exit_code:int|None, enabled:bool, meta:str, recent_logs:str, error_count:int, is_watched:bool, last_report_at:datetime|None)`(`meta` 存 JSON 字符串)
  - `Tunnel(id:str, frps_host_id:str, name:str, proto:str, remote_port:int|None, client_addr:str|None, client_host_id:str|None, online:bool, traffic_in:int, traffic_out:int, conn_count:int, last_report_at:datetime|None)`
  - `get_engine(db_path:str) -> Engine`
  - `init_db(engine) -> None`(建表)
  - `monitor_id(host_id:str, type:str, name:str) -> str`(稳定 ID = sha1 十六进制)

- [ ] **Step 1: 写失败的测试**

`tests/test_db.py`:
```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_db.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'server.db'`

- [ ] **Step 3: 写最小实现**

`server/db.py`:
```python
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_db.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add server/db.py tests/test_db.py
git commit -m "feat: 定义 Host/Monitor/Tunnel 数据模型与建表"
```

---

### Task 3: 上报入站数据结构(Pydantic schema)

**Files:**
- Create: `server/schemas.py`
- Test: `tests/test_schemas.py`

**Interfaces:**
- Produces:
  - `HostIn(id:str, name:str, platform:str)`
  - `MonitorIn(type:str, name:str, display_name:str|None=None, status:str, started_at:str|None=None, restart_count:int=0, last_exit_code:int|None=None, enabled:bool=False, meta:dict={}, recent_logs:str="")`
  - `TunnelIn(name:str, proto:str, remote_port:int|None=None, client_addr:str|None=None, online:bool=False, traffic_in:int=0, traffic_out:int=0, conn_count:int=0)`
  - `ReportIn(host:HostIn, monitors:list[MonitorIn]=[], tunnels:list[TunnelIn]=[])`

- [ ] **Step 1: 写失败的测试**

`tests/test_schemas.py`:
```python
from server.schemas import ReportIn

def test_parse_report():
    payload = {
        "host": {"id": "mac", "name": "Mac", "platform": "darwin"},
        "monitors": [{
            "type": "launchd", "name": "com.feishu-claude.bot",
            "status": "up", "restart_count": 50, "enabled": True,
            "meta": {"cmd": "python main.py"}, "recent_logs": "ok\n"
        }],
        "tunnels": [{"name": "web", "proto": "tcp", "remote_port": 7001, "online": True}],
    }
    r = ReportIn.model_validate(payload)
    assert r.host.id == "mac"
    assert r.monitors[0].restart_count == 50
    assert r.monitors[0].meta["cmd"] == "python main.py"
    assert r.tunnels[0].remote_port == 7001

def test_defaults_when_minimal():
    r = ReportIn.model_validate({"host": {"id": "x", "name": "X", "platform": "linux"}})
    assert r.monitors == [] and r.tunnels == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_schemas.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'server.schemas'`

- [ ] **Step 3: 写最小实现**

`server/schemas.py`:
```python
from pydantic import BaseModel, Field


class HostIn(BaseModel):
    id: str
    name: str
    platform: str


class MonitorIn(BaseModel):
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
    name: str
    proto: str
    remote_port: int | None = None
    client_addr: str | None = None
    online: bool = False
    traffic_in: int = 0
    traffic_out: int = 0
    conn_count: int = 0


class ReportIn(BaseModel):
    host: HostIn
    monitors: list[MonitorIn] = Field(default_factory=list)
    tunnels: list[TunnelIn] = Field(default_factory=list)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_schemas.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add server/schemas.py tests/test_schemas.py
git commit -m "feat: 定义上报入站数据结构"
```

---

### Task 4: 上报处理核心逻辑(upsert + error_count,纯函数)

**Files:**
- Create: `server/ingest.py`
- Test: `tests/test_ingest.py`

**Interfaces:**
- Consumes: `server.db`(Host/Monitor/Tunnel/monitor_id)、`server.schemas.ReportIn`
- Produces:
  - `count_errors(text:str, pattern:str=DEFAULT_ERROR_PATTERN) -> int`
  - `DEFAULT_ERROR_PATTERN: str`
  - `ingest_report(session, report:ReportIn, now:datetime) -> None`
    - upsert host(更新 name/platform/last_seen=now)
    - 每个 monitor:id=monitor_id(...);新建或更新 status/started_at/restart_count/last_exit_code/enabled/meta(json.dumps)/recent_logs/error_count/last_report_at=now;**保留**已存在记录的 `is_watched` 与用户设置的 `display_name`(上报的 display_name 为 None 时不覆盖)
    - 每个 tunnel:id=monitor_id(frps_host_id,"tunnel",name);upsert,frps_host_id=report.host.id,online/流量/conn_count/last_report_at=now

- [ ] **Step 1: 写失败的测试**

`tests/test_ingest.py`:
```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_ingest.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'server.ingest'`

- [ ] **Step 3: 写最小实现**

`server/ingest.py`:
```python
import json
import re
from datetime import datetime
from server.db import Host, Monitor, Tunnel, monitor_id
from server.schemas import ReportIn

DEFAULT_ERROR_PATTERN = r"ERROR|Exception|Traceback|panic|fatal|FATAL"


def count_errors(text: str, pattern: str = DEFAULT_ERROR_PATTERN) -> int:
    rx = re.compile(pattern)
    return sum(1 for line in text.splitlines() if rx.search(line))


def ingest_report(session, report: ReportIn, now: datetime) -> None:
    host = session.get(Host, report.host.id)
    if host is None:
        host = Host(id=report.host.id, name=report.host.name, platform=report.host.platform)
    host.name = report.host.name
    host.platform = report.host.platform
    host.last_seen = now
    session.add(host)

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
        if mi.display_name is not None:
            m.display_name = mi.display_name
        session.add(m)

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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_ingest.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add server/ingest.py tests/test_ingest.py
git commit -m "feat: 实现上报 upsert 与错误计数逻辑"
```

---

### Task 5: 失联状态派生(纯函数)

**Files:**
- Create: `server/status.py`
- Test: `tests/test_status.py`

**Interfaces:**
- Consumes: `server.db.Monitor`
- Produces:
  - `STALE_SECONDS: int = 90`
  - `effective_status(m:Monitor, now:datetime) -> str`:`last_report_at` 为空或距 now 超过 `STALE_SECONDS` 返回 `"unknown"`,否则返回 `m.status`
  - `tunnel_online(t:Tunnel, now:datetime) -> bool`:失联超阈值视为离线,否则返回 `t.online`

- [ ] **Step 1: 写失败的测试**

`tests/test_status.py`:
```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_status.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'server.status'`

- [ ] **Step 3: 写最小实现**

`server/status.py`:
```python
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_status.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add server/status.py tests/test_status.py
git commit -m "feat: 实现失联状态派生逻辑"
```

---

### Task 6: 应用装配——DB 会话、配置、POST /api/report

**Files:**
- Modify: `server/main.py`
- Create: `server/deps.py`
- Test: `tests/test_report_api.py`

**Interfaces:**
- Consumes: `server.db`、`server.ingest.ingest_report`、`server.schemas.ReportIn`
- Produces:
  - `server.deps.get_session`(FastAPI 依赖,yield Session)
  - `server.deps.now()`(返回 `datetime.now()`,可在测试中 monkeypatch)
  - `server.deps.require_token(x_monitor_token: str = Header(...))`(校验 `X-Monitor-Token` == `MONITOR_TOKEN`,否则 401)
  - `POST /api/report`:校验 token → ingest → commit → 返回 `{"ok": true}`
  - `app` 在 startup 时 `init_db`

- [ ] **Step 1: 写失败的测试**

`tests/test_report_api.py`:
```python
import os
os.environ["MONITOR_TOKEN"] = "secret"
os.environ["MONITOR_DB"] = ":memory:"

import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MONITOR_DB", str(tmp_path / "api.db"))
    monkeypatch.setenv("MONITOR_TOKEN", "secret")
    import importlib, server.deps, server.main
    importlib.reload(server.deps); importlib.reload(server.main)
    from server.main import app
    with TestClient(app) as c:
        yield c

PAYLOAD = {
    "host": {"id": "ecs", "name": "ECS", "platform": "linux"},
    "monitors": [{"type": "systemd", "name": "myblog", "status": "up"}],
}

def test_report_requires_token(client):
    assert client.post("/api/report", json=PAYLOAD).status_code == 401

def test_report_ok(client):
    r = client.post("/api/report", json=PAYLOAD, headers={"X-Monitor-Token": "secret"})
    assert r.status_code == 200 and r.json() == {"ok": True}

def test_report_wrong_token(client):
    r = client.post("/api/report", json=PAYLOAD, headers={"X-Monitor-Token": "nope"})
    assert r.status_code == 401
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_report_api.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'server.deps'`

- [ ] **Step 3: 写最小实现**

`server/deps.py`:
```python
import os
from datetime import datetime
from fastapi import Header, HTTPException
from sqlmodel import Session
from server.db import get_engine, init_db

_engine = None


def engine():
    global _engine
    if _engine is None:
        _engine = get_engine(os.environ.get("MONITOR_DB", "monitor.db"))
        init_db(_engine)
    return _engine


def get_session():
    with Session(engine()) as session:
        yield session


def now() -> datetime:
    return datetime.now()


def require_token(x_monitor_token: str = Header(default="")):
    expected = os.environ.get("MONITOR_TOKEN", "")
    if not expected or x_monitor_token != expected:
        raise HTTPException(status_code=401, detail="invalid token")
```

`server/main.py`(替换为):
```python
from fastapi import FastAPI, Depends
from sqlmodel import Session
from server.deps import get_session, now, require_token, engine
from server.schemas import ReportIn
from server.ingest import ingest_report

app = FastAPI(title="Monitor")


@app.on_event("startup")
def _startup():
    engine()  # 触发建表


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/report")
def report(payload: ReportIn, session: Session = Depends(get_session),
           _=Depends(require_token)):
    ingest_report(session, payload, now())
    session.commit()
    return {"ok": True}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_report_api.py -v`
Expected: PASS

- [ ] **Step 5: 运行全部测试**

Run: `python -m pytest -v`
Expected: 全部 PASS

- [ ] **Step 6: 提交**

```bash
git add server/main.py server/deps.py tests/test_report_api.py
git commit -m "feat: 装配上报接口与 token 鉴权"
```

---

### Task 7: 只读查询层(overview / host-all / monitor detail / tunnels,纯函数)

**Files:**
- Create: `server/queries.py`
- Test: `tests/test_queries.py`

**Interfaces:**
- Consumes: `server.db`、`server.status.effective_status`、`server.status.tunnel_online`
- Produces(均返回普通 dict/list,字段名固定,供 API 与模板复用):
  - `overview(session, now) -> dict`:`{"summary": {"total","up","down","unknown","errors"}, "hosts": [{"id","name","platform","last_seen","monitors":[<row>...]}], "tunnels_online": int}`,其中 monitors 只含 `is_watched=True` 的;`<row>` = `{"id","display_name"|"name","type","eff_status","restart_count","error_count","last_report_at"}`
  - `host_all(session, host_id, now) -> list[<row>]`:某 host **全部** monitor(含未关注),`<row>` 额外含 `is_watched`
  - `monitor_detail(session, mid, now) -> dict|None`:单对象全字段 + `eff_status` + `meta`(解析回 dict)
  - `tunnels(session, now) -> list[dict]`:每条 `{"name","proto","remote_port","client_addr","online":<派生>,"traffic_in","traffic_out","conn_count","frps_host_id"}`
  - 辅助:`display_of(m) -> str` 返回 `m.display_name or m.name`

- [ ] **Step 1: 写失败的测试**

`tests/test_queries.py`:
```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_queries.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'server.queries'`

- [ ] **Step 3: 写最小实现**

`server/queries.py`:
```python
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_queries.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add server/queries.py tests/test_queries.py
git commit -m "feat: 实现只读查询层"
```

---

### Task 8: 只读 JSON API + 关注切换 + 改名

**Files:**
- Create: `server/api.py`
- Modify: `server/main.py`(`app.include_router`)
- Test: `tests/test_readapi.py`

**Interfaces:**
- Consumes: `server.queries`、`server.deps.get_session`、`server.deps.now`、`server.db.Monitor`
- Produces(`APIRouter`,prefix `/api`):
  - `GET /api/overview` → `queries.overview`
  - `GET /api/hosts/{host_id}/all` → `queries.host_all`
  - `GET /api/monitors/{mid}` → `queries.monitor_detail`(404 当 None)
  - `POST /api/monitors/{mid}/watch` body `{"watched": bool}` → 更新 `is_watched`,返回 `{"ok":true,"is_watched":bool}`
  - `PATCH /api/monitors/{mid}` body `{"display_name": str}` → 更新,返回 `{"ok":true}`
  - `GET /api/tunnels` → `queries.tunnels`
  - 这些读接口**不需要** token(仅本人浏览器内网/HTTPS 访问)

- [ ] **Step 1: 写失败的测试**

`tests/test_readapi.py`:
```python
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MONITOR_DB", str(tmp_path / "r.db"))
    monkeypatch.setenv("MONITOR_TOKEN", "secret")
    import importlib, server.deps, server.api, server.main
    importlib.reload(server.deps); importlib.reload(server.api); importlib.reload(server.main)
    from server.main import app
    with TestClient(app) as c:
        c.post("/api/report", headers={"X-Monitor-Token": "secret"}, json={
            "host": {"id": "ecs", "name": "ECS", "platform": "linux"},
            "monitors": [{"type": "systemd", "name": "myblog", "status": "up"}],
        })
        yield c

def _mid(c):
    return c.get("/api/hosts/ecs/all").json()[0]["id"]

def test_overview(client):
    ov = client.get("/api/overview").json()
    assert ov["summary"]["total"] == 0  # 默认未关注

def test_watch_then_overview(client):
    mid = _mid(client)
    r = client.post(f"/api/monitors/{mid}/watch", json={"watched": True})
    assert r.json()["is_watched"] is True
    assert client.get("/api/overview").json()["summary"]["total"] == 1

def test_rename(client):
    mid = _mid(client)
    client.patch(f"/api/monitors/{mid}", json={"display_name": "我的博客"})
    assert client.get(f"/api/monitors/{mid}").json()["display_name"] == "我的博客"

def test_detail_404(client):
    assert client.get("/api/monitors/nope").status_code == 404
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_readapi.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'server.api'`

- [ ] **Step 3: 写最小实现**

`server/api.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session
from server.deps import get_session, now
from server.db import Monitor
from server import queries

router = APIRouter(prefix="/api")


class WatchIn(BaseModel):
    watched: bool


class RenameIn(BaseModel):
    display_name: str


@router.get("/overview")
def get_overview(session: Session = Depends(get_session)):
    return queries.overview(session, now())


@router.get("/hosts/{host_id}/all")
def get_host_all(host_id: str, session: Session = Depends(get_session)):
    return queries.host_all(session, host_id, now())


@router.get("/monitors/{mid}")
def get_monitor(mid: str, session: Session = Depends(get_session)):
    d = queries.monitor_detail(session, mid, now())
    if d is None:
        raise HTTPException(404, "not found")
    return d


@router.post("/monitors/{mid}/watch")
def set_watch(mid: str, body: WatchIn, session: Session = Depends(get_session)):
    m = session.get(Monitor, mid)
    if m is None:
        raise HTTPException(404, "not found")
    m.is_watched = body.watched
    session.add(m); session.commit()
    return {"ok": True, "is_watched": m.is_watched}


@router.patch("/monitors/{mid}")
def rename(mid: str, body: RenameIn, session: Session = Depends(get_session)):
    m = session.get(Monitor, mid)
    if m is None:
        raise HTTPException(404, "not found")
    m.display_name = body.display_name
    session.add(m); session.commit()
    return {"ok": True}


@router.get("/tunnels")
def get_tunnels(session: Session = Depends(get_session)):
    return queries.tunnels(session, now())
```

在 `server/main.py` 顶部 import 后加入(在 `report` 路由定义之后):
```python
from server.api import router as api_router
app.include_router(api_router)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_readapi.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add server/api.py server/main.py tests/test_readapi.py
git commit -m "feat: 实现只读 JSON API 与关注/改名接口"
```

---

### Task 9: 概览页(首页模板 + 轮询刷新)

**Files:**
- Create: `server/templates/base.html`
- Create: `server/templates/overview.html`
- Create: `server/static/app.js`
- Modify: `server/main.py`(挂载 static + Jinja2 + `GET /`)
- Test: `tests/test_pages.py`

**Interfaces:**
- Consumes: `server.queries.overview`、`server.deps.get_session`/`now`
- Produces:
  - `GET /` 返回概览页 HTML(状态码 200,含汇总数字与各 host 分组)
  - `base.html` 提供公共骨架(中文标题、Tailwind CDN、导航:概览/隧道拓扑)
  - `static/app.js` 每 10 秒轮询 `/api/overview` 并更新页面 DOM

- [ ] **Step 1: 写失败的测试**

`tests/test_pages.py`:
```python
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MONITOR_DB", str(tmp_path / "p.db"))
    monkeypatch.setenv("MONITOR_TOKEN", "secret")
    import importlib, server.deps, server.api, server.main
    importlib.reload(server.deps); importlib.reload(server.api); importlib.reload(server.main)
    from server.main import app
    with TestClient(app) as c:
        c.post("/api/report", headers={"X-Monitor-Token": "secret"}, json={
            "host": {"id": "ecs", "name": "ECS", "platform": "linux"},
            "monitors": [{"type": "systemd", "name": "myblog", "status": "up"}],
        })
        yield c

def test_overview_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "概览" in r.text
    assert "ECS" in r.text
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_pages.py -v`
Expected: FAIL（500 或断言失败,因 `/` 未定义)

- [ ] **Step 3: 写最小实现**

`server/templates/base.html`:
```html
<!doctype html>
<html lang="zh">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Monitor{% endblock %}</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 text-slate-800">
  <nav class="bg-slate-900 text-white px-6 py-3 flex gap-6">
    <span class="font-bold">监控面板</span>
    <a href="/" class="hover:underline">概览</a>
    <a href="/tunnels" class="hover:underline">隧道拓扑</a>
  </nav>
  <main class="p-6 max-w-5xl mx-auto">{% block body %}{% endblock %}</main>
  {% block scripts %}{% endblock %}
</body>
</html>
```

`server/templates/overview.html`:
```html
{% extends "base.html" %}
{% block title %}概览 · Monitor{% endblock %}
{% block body %}
<h1 class="text-2xl font-bold mb-4">全局概览</h1>
<div id="summary" class="flex gap-4 mb-6">
  <div class="bg-white rounded shadow px-4 py-3">关注 <b>{{ ov.summary.total }}</b></div>
  <div class="bg-white rounded shadow px-4 py-3 text-green-600">运行 <b>{{ ov.summary.up }}</b></div>
  <div class="bg-white rounded shadow px-4 py-3 text-red-600">挂了 <b>{{ ov.summary.down }}</b></div>
  <div class="bg-white rounded shadow px-4 py-3 text-slate-400">失联 <b>{{ ov.summary.unknown }}</b></div>
  <div class="bg-white rounded shadow px-4 py-3 text-amber-600">报错 <b>{{ ov.summary.errors }}</b></div>
  <a href="/tunnels" class="bg-white rounded shadow px-4 py-3">隧道在线 <b>{{ ov.tunnels_online }}</b></a>
</div>
{% for h in ov.hosts %}
<section class="mb-6">
  <h2 class="text-lg font-semibold mb-2">{{ h.name }} <span class="text-xs text-slate-400">{{ h.platform }}</span>
    <a href="/hosts/{{ h.id }}" class="text-sm text-blue-600 ml-2">发现…</a></h2>
  <table class="w-full bg-white rounded shadow text-sm">
    <thead><tr class="text-left border-b">
      <th class="p-2">状态</th><th>名称</th><th>类型</th><th>重启</th><th>报错</th><th>最后上报</th></tr></thead>
    <tbody>
    {% for m in h.monitors %}
      <tr class="border-b hover:bg-slate-50">
        <td class="p-2">{{ {"up":"🟢","down":"🔴","unknown":"⚪"}[m.eff_status] }}</td>
        <td><a class="text-blue-600" href="/monitors/{{ m.id }}">{{ m.name }}</a></td>
        <td>{{ m.type }}</td>
        <td class="{{ 'text-red-600 font-bold' if m.restart_count >= 10 else '' }}">{{ m.restart_count }}</td>
        <td class="{{ 'text-amber-600' if m.error_count else '' }}">{{ m.error_count }}</td>
        <td class="text-slate-400">{{ m.last_report_at }}</td>
      </tr>
    {% else %}
      <tr><td colspan="6" class="p-2 text-slate-400">暂无关注对象,去"发现…"添加</td></tr>
    {% endfor %}
    </tbody>
  </table>
</section>
{% endfor %}
{% endblock %}
{% block scripts %}<script src="/static/app.js"></script>{% endblock %}
```

`server/static/app.js`:
```javascript
// 每 10 秒刷新概览数字(简单整页轮询;DOM 局部更新留待后续增强)
async function refresh() {
  try {
    const ov = await (await fetch("/api/overview")).json();
    const s = ov.summary;
    document.title = `概览(${s.up}↑/${s.down}↓)· Monitor`;
  } catch (e) { /* 忽略瞬时网络错误 */ }
}
setInterval(refresh, 10000);
```

在 `server/main.py` 中加入(import 区与路由区):
```python
from pathlib import Path
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

_BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(_BASE / "templates"))
app.mount("/static", StaticFiles(directory=str(_BASE / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
def page_overview(request: Request, session: Session = Depends(get_session)):
    ov = queries.overview(session, now())
    return templates.TemplateResponse("overview.html", {"request": request, "ov": ov})
```
并补充顶部 import:`from server import queries`。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_pages.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add server/templates/base.html server/templates/overview.html server/static/app.js server/main.py tests/test_pages.py
git commit -m "feat: 实现全局概览页"
```

---

### Task 10: 发现页(列出某 host 全部对象 + 关注切换)

**Files:**
- Create: `server/templates/host.html`
- Modify: `server/main.py`(`GET /hosts/{host_id}`)
- Modify: `server/static/app.js`(新增 `toggleWatch`)
- Test: `tests/test_host_page.py`

**Interfaces:**
- Consumes: `server.queries.host_all`、`POST /api/monitors/{mid}/watch`
- Produces: `GET /hosts/{host_id}` 渲染该 host 全部对象(含未关注),每行一个"关注/取消"按钮,调用 `/api/monitors/{mid}/watch`

- [ ] **Step 1: 写失败的测试**

`tests/test_host_page.py`:
```python
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MONITOR_DB", str(tmp_path / "h.db"))
    monkeypatch.setenv("MONITOR_TOKEN", "secret")
    import importlib, server.deps, server.api, server.main
    importlib.reload(server.deps); importlib.reload(server.api); importlib.reload(server.main)
    from server.main import app
    with TestClient(app) as c:
        c.post("/api/report", headers={"X-Monitor-Token": "secret"}, json={
            "host": {"id": "ecs", "name": "ECS", "platform": "linux"},
            "monitors": [{"type": "systemd", "name": "myblog", "status": "up"},
                         {"type": "systemd", "name": "redis", "status": "up"}],
        })
        yield c

def test_host_page_lists_all(client):
    r = client.get("/hosts/ecs")
    assert r.status_code == 200
    assert "myblog" in r.text and "redis" in r.text
    assert "关注" in r.text
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_host_page.py -v`
Expected: FAIL（404,`/hosts/{id}` 未定义)

- [ ] **Step 3: 写最小实现**

`server/templates/host.html`:
```html
{% extends "base.html" %}
{% block title %}发现 · {{ host_id }}{% endblock %}
{% block body %}
<h1 class="text-2xl font-bold mb-4">发现 — {{ host_id }}</h1>
<p class="text-slate-500 mb-4 text-sm">勾选你关心的对象,它们会出现在全局概览。</p>
<table class="w-full bg-white rounded shadow text-sm">
  <thead><tr class="text-left border-b"><th class="p-2">状态</th><th>名称</th><th>类型</th><th>关注</th></tr></thead>
  <tbody>
  {% for m in rows %}
    <tr class="border-b" data-mid="{{ m.id }}">
      <td class="p-2">{{ {"up":"🟢","down":"🔴","unknown":"⚪"}[m.eff_status] }}</td>
      <td><a class="text-blue-600" href="/monitors/{{ m.id }}">{{ m.name }}</a></td>
      <td>{{ m.type }}</td>
      <td><button class="watch-btn px-2 py-1 rounded {{ 'bg-green-600 text-white' if m.is_watched else 'bg-slate-200' }}"
                  data-mid="{{ m.id }}" data-watched="{{ 'true' if m.is_watched else 'false' }}">
        {{ '已关注' if m.is_watched else '关注' }}</button></td>
    </tr>
  {% endfor %}
  </tbody>
</table>
{% endblock %}
{% block scripts %}<script src="/static/app.js"></script>{% endblock %}
```

在 `server/static/app.js` 末尾追加:
```javascript
async function toggleWatch(btn) {
  const mid = btn.dataset.mid;
  const next = btn.dataset.watched !== "true";
  await fetch(`/api/monitors/${mid}/watch`, {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({watched: next}),
  });
  location.reload();
}
document.addEventListener("click", (e) => {
  if (e.target.classList.contains("watch-btn")) toggleWatch(e.target);
});
```

在 `server/main.py` 路由区加入:
```python
@app.get("/hosts/{host_id}", response_class=HTMLResponse)
def page_host(host_id: str, request: Request, session: Session = Depends(get_session)):
    rows = queries.host_all(session, host_id, now())
    return templates.TemplateResponse("host.html",
        {"request": request, "host_id": host_id, "rows": rows})
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_host_page.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add server/templates/host.html server/static/app.js server/main.py tests/test_host_page.py
git commit -m "feat: 实现发现页与关注切换"
```

---

### Task 11: 明细页(配置 + 日志,错误高亮)

**Files:**
- Create: `server/templates/monitor.html`
- Modify: `server/main.py`(`GET /monitors/{mid}`)
- Test: `tests/test_monitor_page.py`

**Interfaces:**
- Consumes: `server.queries.monitor_detail`
- Produces: `GET /monitors/{mid}` 渲染单对象明细:顶部状态/重启/启动时间/自启;配置区遍历 `meta`;日志区按行渲染,命中错误正则的行加红色样式。404 当对象不存在。

- [ ] **Step 1: 写失败的测试**

`tests/test_monitor_page.py`:
```python
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MONITOR_DB", str(tmp_path / "m.db"))
    monkeypatch.setenv("MONITOR_TOKEN", "secret")
    import importlib, server.deps, server.api, server.main
    importlib.reload(server.deps); importlib.reload(server.api); importlib.reload(server.main)
    from server.main import app
    with TestClient(app) as c:
        c.post("/api/report", headers={"X-Monitor-Token": "secret"}, json={
            "host": {"id": "ecs", "name": "ECS", "platform": "linux"},
            "monitors": [{"type": "systemd", "name": "myblog", "status": "up",
                          "meta": {"cmd": "java -jar x.jar"},
                          "recent_logs": "started ok\nERROR boom"}],
        })
        yield c

def _mid(c):
    return c.get("/api/hosts/ecs/all").json()[0]["id"]

def test_monitor_page(client):
    r = client.get(f"/monitors/{_mid(client)}")
    assert r.status_code == 200
    assert "java -jar x.jar" in r.text
    assert "ERROR boom" in r.text

def test_monitor_page_404(client):
    assert client.get("/monitors/nope").status_code == 404
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_monitor_page.py -v`
Expected: FAIL（404 路由未定义 / 断言失败)

- [ ] **Step 3: 写最小实现**

`server/templates/monitor.html`:
```html
{% extends "base.html" %}
{% block title %}{{ d.name }} · 明细{% endblock %}
{% block body %}
<a href="/hosts/{{ d.host_id }}" class="text-sm text-blue-600">← 返回 {{ d.host_id }}</a>
<h1 class="text-2xl font-bold my-3">
  {{ {"up":"🟢","down":"🔴","unknown":"⚪"}[d.eff_status] }}
  {{ d.display_name or d.name }}
</h1>
<div class="grid grid-cols-2 gap-3 mb-6 text-sm">
  <div class="bg-white rounded shadow p-3">类型:{{ d.type }}</div>
  <div class="bg-white rounded shadow p-3">重启次数:
    <b class="{{ 'text-red-600' if d.restart_count >= 10 else '' }}">{{ d.restart_count }}</b></div>
  <div class="bg-white rounded shadow p-3">启动时间:{{ d.started_at or "—" }}</div>
  <div class="bg-white rounded shadow p-3">开机自启:{{ "是" if d.enabled else "否" }}</div>
</div>
<h2 class="font-semibold mb-2">配置</h2>
<table class="w-full bg-white rounded shadow text-sm mb-6">
  {% for k, v in d.meta.items() %}
  <tr class="border-b"><td class="p-2 text-slate-500 w-40">{{ k }}</td><td class="p-2">{{ v }}</td></tr>
  {% endfor %}
</table>
<h2 class="font-semibold mb-2">最近日志(报错 {{ d.error_count }} 行)</h2>
<pre class="bg-slate-900 text-slate-100 rounded p-3 text-xs overflow-auto max-h-96">{% for line in log_lines %}<span class="{{ 'text-red-400' if line.error else '' }}">{{ line.text }}</span>
{% endfor %}</pre>
{% endblock %}
```

在 `server/main.py` 路由区加入(复用 `ingest.count_errors` 的正则做行级高亮):
```python
import re as _re
from server.ingest import DEFAULT_ERROR_PATTERN
_ERR_RX = _re.compile(DEFAULT_ERROR_PATTERN)


@app.get("/monitors/{mid}", response_class=HTMLResponse)
def page_monitor(mid: str, request: Request, session: Session = Depends(get_session)):
    d = queries.monitor_detail(session, mid, now())
    if d is None:
        raise HTTPException(404, "not found")
    log_lines = [{"text": ln, "error": bool(_ERR_RX.search(ln))}
                 for ln in d["recent_logs"].splitlines()]
    return templates.TemplateResponse("monitor.html",
        {"request": request, "d": d, "log_lines": log_lines})
```
补充 `server/main.py` 顶部 import:`from fastapi import HTTPException`。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_monitor_page.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add server/templates/monitor.html server/main.py tests/test_monitor_page.py
git commit -m "feat: 实现对象明细页与日志错误高亮"
```

---

### Task 12: 隧道拓扑页

**Files:**
- Create: `server/templates/tunnels.html`
- Modify: `server/main.py`(`GET /tunnels`)
- Test: `tests/test_tunnels_page.py`

**Interfaces:**
- Consumes: `server.queries.tunnels`
- Produces: `GET /tunnels` 渲染隧道列表,每条显示 `客户端 → 暴露端口`、proto、在线状态、今日流量、连接数。

- [ ] **Step 1: 写失败的测试**

`tests/test_tunnels_page.py`:
```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_tunnels_page.py -v`
Expected: FAIL（断言失败或 500)

- [ ] **Step 3: 写最小实现**

`server/templates/tunnels.html`:
```html
{% extends "base.html" %}
{% block title %}隧道拓扑 · Monitor{% endblock %}
{% block body %}
<h1 class="text-2xl font-bold mb-4">内网穿透隧道</h1>
<table class="w-full bg-white rounded shadow text-sm">
  <thead><tr class="text-left border-b">
    <th class="p-2">状态</th><th>隧道</th><th>连接</th><th>协议</th>
    <th>暴露端口</th><th>客户端</th><th>连接数</th><th>今日流量(↓/↑)</th></tr></thead>
  <tbody>
  {% for t in tunnels %}
    <tr class="border-b">
      <td class="p-2">{{ "🟢" if t.online else "⚪" }}</td>
      <td>{{ t.name }}</td>
      <td class="text-slate-500">{{ t.client_addr or "?" }} → {{ t.frps_host_id }}</td>
      <td>{{ t.proto }}</td>
      <td>{{ t.remote_port or "—" }}</td>
      <td>{{ t.client_addr or "—" }}</td>
      <td>{{ t.conn_count }}</td>
      <td>{{ t.traffic_in }}/{{ t.traffic_out }}</td>
    </tr>
  {% else %}
    <tr><td colspan="8" class="p-2 text-slate-400">暂无隧道数据</td></tr>
  {% endfor %}
  </tbody>
</table>
{% endblock %}
```

在 `server/main.py` 路由区加入:
```python
@app.get("/tunnels", response_class=HTMLResponse)
def page_tunnels(request: Request, session: Session = Depends(get_session)):
    ts = queries.tunnels(session, now())
    return templates.TemplateResponse("tunnels.html", {"request": request, "tunnels": ts})
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_tunnels_page.py -v`
Expected: PASS

- [ ] **Step 5: 运行全部测试**

Run: `python -m pytest -v`
Expected: 全部 PASS

- [ ] **Step 6: 提交**

```bash
git add server/templates/tunnels.html server/main.py tests/test_tunnels_page.py
git commit -m "feat: 实现隧道拓扑页"
```

---

### Task 13: 运行说明与 README

**Files:**
- Create: `README.md`
- Create: `server/run.sh`

**Interfaces:**
- Produces: 本地启动 server 的可执行说明。

- [ ] **Step 1: 写 README**

`README.md`:
```markdown
# Monitor

自建轻量监控面板:统一监控本机与 ECS 上自部署的项目(存活/日志/配置)+ frp 隧道拓扑。

## 中心 server

### 本地运行
```bash
pip install -r requirements-dev.txt
export MONITOR_TOKEN=$(openssl rand -hex 16)   # agent 上报用的共享密钥
export MONITOR_DB=monitor.db
uvicorn server.main:app --host 0.0.0.0 --port 8800
```
浏览器打开 http://localhost:8800

### 测试
```bash
python -m pytest -v
```

## agent
见 Plan 2(`docs/superpowers/plans/*-monitor-agent.md`)。
```

`server/run.sh`:
```bash
#!/usr/bin/env bash
set -e
export MONITOR_DB="${MONITOR_DB:-monitor.db}"
exec uvicorn server.main:app --host 0.0.0.0 --port "${MONITOR_PORT:-8800}"
```

- [ ] **Step 2: 运行全部测试确认未破坏**

Run: `python -m pytest -v`
Expected: 全部 PASS

- [ ] **Step 3: 提交**

```bash
chmod +x server/run.sh
git add README.md server/run.sh
git commit -m "docs: 添加 server 运行说明与启动脚本"
```

---

## Self-Review 记录

- **Spec 覆盖**:上报(Task 4/6)、数据模型 hosts/monitors/tunnels(Task 2)、失联派生(Task 5)、关注机制(Task 7/8/10)、错误识别(Task 4/11)、4 个页面 概览/拓扑/发现/明细(Task 9/12/10/11)、API 全集(Task 6/8)、技术栈 FastAPI+SQLModel+Jinja2(贯穿)、部署启动(Task 13)。frp 探针的**采集**属 agent(Plan 2),server 端只负责接收 tunnels(Task 4)与展示(Task 12)——已覆盖。
- **占位符扫描**:无 TBD/TODO,每个代码步骤含完整代码。
- **类型一致性**:`monitor_id`、`effective_status`、`tunnel_online`、`queries.overview/host_all/monitor_detail/tunnels`、`_row` 字段(`eff_status`/`is_watched`/`restart_count`)在各任务间一致。
