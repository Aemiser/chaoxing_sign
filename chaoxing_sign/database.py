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
    engine = create_engine(
        url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
        connect_args={"connect_timeout": 5},
    )
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return engine


def get_db() -> Session:
    """获取数据库会话（从连接池复用连接）"""
    if SessionLocal is None:
        raise RuntimeError("Database not initialized")
    return SessionLocal()
