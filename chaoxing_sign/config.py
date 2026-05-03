"""全局配置模块 — Pydantic Settings 类型校验 + dict 兼容层

优先级（高→低）：环境变量 > .env 文件 > 代码默认值

用法:
    from chaoxing_sign.config import config
    phone = config["phone"]
    loc = config.get("location", {})
"""
from __future__ import annotations
import logging
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_ENV_PATH = Path(__file__).parent.parent / ".env"


# ================================================================
# Pydantic 配置模型
# ================================================================

class LocationSettings(BaseSettings):
    """默认签到位置"""
    model_config = SettingsConfigDict(extra="ignore")
    longitude: str = "116.404"
    latitude: str = "39.915"
    name: str = "北京市"


class DatabaseSettings(BaseSettings):
    """MySQL 连接参数"""
    model_config = SettingsConfigDict(extra="ignore")

    host: str = "localhost"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "chaoxing_sign"

    @property
    def mysql_url(self) -> str:
        return (
            f"mysql+pymysql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}?charset=utf8mb4"
        )


class LogSettings(BaseSettings):
    """日志配置"""
    model_config = SettingsConfigDict(extra="ignore")

    level: str = "INFO"
    console: bool = True
    file: bool = True
    dir: str = "logs"
    max_bytes: int = 10485760
    backup_count: int = 5


class AppSettings(BaseSettings):
    """超星签到应用配置"""

    model_config = SettingsConfigDict(
        env_file=_ENV_PATH,
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # --------- 账号 ---------
    CHAOXING_PHONE: str = ""
    CHAOXING_PASSWORD: str = ""

    # --------- 子配置 ---------
    location: LocationSettings = Field(default_factory=LocationSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    log: LogSettings = Field(default_factory=LogSettings)

    # --------- JWT ---------
    jwt_secret: str = ""

    # --------- 高德地图 ---------
    amap_key: str = ""
    amap_key_info: str = ""
    amap_version: str = "2.0"

    # --------- 腾讯地图 ---------
    tmap_key: str = ""

    # --------- RSA 加密密钥 ---------
    rsa_private_key_path: str = "rsa_key.pem"
    rsa_public_key_path: str = "rsa_key.pub.pem"

    # --------- Redis ---------
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    # --------- 签到 ---------
    sign__show_trilateration: bool = True

    @property
    def phone(self) -> str:
        return self.CHAOXING_PHONE

    @property
    def password(self) -> str:
        return self.CHAOXING_PASSWORD

    def to_dict(self) -> dict:
        """转换为 dict 以兼容旧代码"""
        return {
            "phone": self.CHAOXING_PHONE,
            "password": self.CHAOXING_PASSWORD,
            "location": {
                "longitude": self.location.longitude,
                "latitude": self.location.latitude,
                "name": self.location.name,
            },
            "database": {
                "host": self.database.host,
                "port": self.database.port,
                "user": self.database.user,
                "password": self.database.password,
                "database": self.database.database,
            },
            "jwt_secret": self.jwt_secret,
            "rsa_private_key_path": self.rsa_private_key_path,
            "rsa_public_key_path": self.rsa_public_key_path,
            "amap_key": self.amap_key,
            "amap_key_info": self.amap_key_info,
            "amap_version": self.amap_version,
            "tmap_key": self.tmap_key,
            "redis": {
                "host": self.redis_host,
                "port": self.redis_port,
                "db": self.redis_db,
                "password": self.redis_password,
            },
            "sign": {
                "show_trilateration": self.sign__show_trilateration,
            },
            "log": {
                "level": self.log.level,
                "console": self.log.console,
                "file": self.log.file,
                "dir": self.log.dir,
                "max_bytes": self.log.max_bytes,
                "backup_count": self.log.backup_count,
            },
        }


# ================================================================
# 向后兼容：dict 风格全局单例
# ================================================================

class AppConfig(dict):
    """应用配置（dict 子类，向后兼容旧代码的 config["key"] 访问方式）

    内部由 AppSettings (Pydantic Settings) 驱动。
    """

    def __init__(self):
        super().__init__(AppSettings().to_dict())

    def reload(self):
        """重新加载配置文件"""
        self.clear()
        self.update(AppSettings().to_dict())
        logger.info("配置已重新加载")


config = AppConfig()
