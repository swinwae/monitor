from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session
from server.deps import get_session, now, require_token, engine
from server.schemas import ReportIn
from server.ingest import ingest_report
from server import queries


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时触发建表,关闭时无需额外清理"""
    engine()  # 触发 init_db 建表
    yield


app = FastAPI(title="Monitor", lifespan=lifespan)

_BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(_BASE / "templates"))
app.mount("/static", StaticFiles(directory=str(_BASE / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
def page_overview(request: Request, session: Session = Depends(get_session)):
    """渲染全局概览页"""
    ov = queries.overview(session, now())
    return templates.TemplateResponse(request, "overview.html", {"ov": ov})


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/report")
def report(
    payload: ReportIn,
    session: Session = Depends(get_session),
    _=Depends(require_token),
):
    """接收 agent 上报,写入数据库"""
    ingest_report(session, payload, now())
    session.commit()
    return {"ok": True}


@app.get("/hosts/{host_id}", response_class=HTMLResponse)
def page_host(host_id: str, request: Request, session: Session = Depends(get_session)):
    """渲染发现页:列出某 host 全部监控对象(含未关注)"""
    rows = queries.host_all(session, host_id, now())
    return templates.TemplateResponse(request, "host.html", {"host_id": host_id, "rows": rows})


from server.api import router as api_router
app.include_router(api_router)
