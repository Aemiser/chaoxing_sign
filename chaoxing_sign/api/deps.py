"""FastAPI 依赖注入"""
from __future__ import annotations

from fastapi import HTTPException, Query

from .. import database as db_module
from ..auth.session import SessionManager

# 全局 session 管理器（在 app.py 的 lifespan 中初始时可用）
session_manager: SessionManager | None = None


def get_client(token: str = Query(...)):
    """从 session 池获取已登录的 ChaoxingClient"""
    if session_manager is None:
        raise HTTPException(503, "服务未就绪")
    return session_manager.get(token)


def require_db():
    if db_module.engine is None:
        raise HTTPException(503, "数据库服务不可用，请稍后重试")


def get_db():
    return db_module.get_db()
