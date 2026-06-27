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
