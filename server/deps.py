import os
from datetime import datetime
from fastapi import Header, HTTPException
from sqlmodel import Session
from server.db import get_engine, init_db

# 模块级全局 engine 实例,通过 importlib.reload 可重置
_engine = None


def engine():
    """获取或初始化 SQLite engine,并在首次调用时建表"""
    global _engine
    if _engine is None:
        _engine = get_engine(os.environ.get("MONITOR_DB", "monitor.db"))
        init_db(_engine)
    return _engine


def get_session():
    """FastAPI 依赖:提供数据库 Session,用完自动关闭"""
    with Session(engine()) as session:
        yield session


def now() -> datetime:
    """返回当前时间,可在测试中 monkeypatch 替换"""
    return datetime.now()


def require_token(x_monitor_token: str = Header(default="")):
    """校验请求头 X-Monitor-Token,未配置 MONITOR_TOKEN 或不匹配则返回 401"""
    expected = os.environ.get("MONITOR_TOKEN", "")
    if not expected or x_monitor_token != expected:
        raise HTTPException(status_code=401, detail="invalid token")
