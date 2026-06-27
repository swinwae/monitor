from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from sqlmodel import Session
from server.deps import get_session, now, require_token, engine
from server.schemas import ReportIn
from server.ingest import ingest_report


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时触发建表,关闭时无需额外清理"""
    engine()  # 触发 init_db 建表
    yield


app = FastAPI(title="Monitor", lifespan=lifespan)


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
