"""SQLAlchemy 数据库引擎和会话管理"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

engine = None
SessionLocal: sessionmaker[Session] | None = None


def init_db(config: dict):
    """初始化数据库连接"""
    global engine, SessionLocal
    db_cfg = config.get("database", {})
    url = (
        f"mysql+pymysql://{db_cfg.get('user', 'root')}:{db_cfg.get('password', '')}"
        f"@{db_cfg.get('host', 'localhost')}:{db_cfg.get('port', 3306)}"
        f"/{db_cfg.get('database', 'chaoxing_sign')}?charset=utf8mb4"
    )
    engine = create_engine(url, pool_pre_ping=True, pool_recycle=3600)
    SessionLocal = sessionmaker(bind=engine)
    return engine


def get_db() -> Session:
    """FastAPI 依赖注入：获取数据库会话"""
    if SessionLocal is None:
        raise RuntimeError("Database not initialized")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
