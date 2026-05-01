"""FastAPI 应用工厂"""
from __future__ import annotations
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .. import database as db_module
from ..models import Base
from ..auth.session import SessionManager

from . import deps
from .router_auth import router as auth_router, init as auth_init
from .router_courses import router as courses_router
from .router_sign import router as sign_router
from .router_friends import router as friends_router
from .router_config import router as config_router

log = logging.getLogger(__name__)


def create_app() -> FastAPI:
    session_manager = SessionManager()
    static_dir = Path(__file__).parent.parent.parent / "static"

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 启动
        try:
            from ..config import config as cfg
            db_module.init_db(cfg)
            Base.metadata.create_all(bind=db_module.engine)
            test_db = db_module.SessionLocal()
            test_db.close()
            deps.session_manager = session_manager
            auth_init(session_manager)
            log.info("数据库连接成功，好友/代签功能已启用")
        except Exception as e:
            log.warning("数据库不可用，好友/代签功能已禁用: %s", e)
        yield

    app = FastAPI(title="超星学习通签到", version="4.0", lifespan=lifespan)

    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)
    app.include_router(courses_router)
    app.include_router(sign_router)
    app.include_router(friends_router)
    app.include_router(config_router)

    return app
