"""全局日志配置 — 控制台 + 文件双输出，支持 info/error 分级文件"""
from __future__ import annotations
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler


class ColoredFormatter(logging.Formatter):
    """控制台彩色日志格式 — 使用 record 副本避免影响其他 handler"""

    COLORS = {
        logging.DEBUG: "\033[36m",
        logging.INFO: "\033[32m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[35m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        clone = logging.makeLogRecord(record.__dict__)
        color = self.COLORS.get(clone.levelno, "")
        clone.levelname = f"{color}{clone.levelname}{self.RESET}"
        clone.name = f"\033[1m{clone.name}\033[0m"
        return super().format(clone)


# 防止重复初始化
_logger_initialized = False


def init_logging(config: dict | None = None) -> logging.Logger:
    """初始化全局日志系统 — 幂等，重复调用不重复创建 handler

    配置从 config dict 读取，key 路径:
        config["log"]["level"]       — 日志级别 (默认 INFO)
        config["log"]["console"]     — 是否输出到控制台 (默认 True)
        config["log"]["file"]        — 是否输出到文件 (默认 True)
        config["log"]["dir"]         — 日志文件目录 (默认 "logs")
        config["log"]["max_bytes"]   — 单个日志文件最大字节 (默认 10MB)
        config["log"]["backup_count"]— 保留的备份文件数 (默认 5)
    """
    global _logger_initialized
    if _logger_initialized:
        return logging.getLogger("chaoxing_sign")

    log_cfg = config.get("log", {}) if config else {}

    level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
    console_enabled = log_cfg.get("console", True)
    file_enabled = log_cfg.get("file", True)
    log_dir = Path(log_cfg.get("dir", "logs"))
    max_bytes = int(log_cfg.get("max_bytes", 10485760))
    backup_count = int(log_cfg.get("backup_count", 5))

    root = logging.getLogger("chaoxing_sign")
    root.setLevel(level)
    root.propagate = False

    # 控制台 Handler
    if console_enabled:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_fmt = ColoredFormatter(
            "%(asctime)s | %(levelname)-18s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(console_fmt)
        root.addHandler(console_handler)

    # 文件 Handler — info 级别（所有日志）
    if file_enabled:
        log_dir.mkdir(parents=True, exist_ok=True)

        info_handler = RotatingFileHandler(
            log_dir / "info.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        info_handler.setLevel(logging.INFO)
        info_fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        info_handler.setFormatter(info_fmt)
        root.addHandler(info_handler)

        # 文件 Handler — error 级别（仅错误及以上）
        error_handler = RotatingFileHandler(
            log_dir / "error.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        error_handler.setFormatter(error_fmt)
        root.addHandler(error_handler)

    # 默认 info 文件也记录 ERROR，方便一个文件看全量
    # error.log 是 ERROR 子集，方便快速排查

    # 降低第三方库日志噪音
    for lib in ("urllib3", "requests", "charset_normalizer", "sqlalchemy.engine"):
        logging.getLogger(lib).setLevel(logging.WARNING)

    _logger_initialized = True
    logger = logging.getLogger("chaoxing_sign")
    logger.info("日志系统初始化完成 level=%s console=%s file=%s dir=%s",
                logging.getLevelName(level), console_enabled, file_enabled, log_dir)
    return logger


def get_logger(name: str) -> logging.Logger:
    """获取 chaoxing_sign 命名空间下的日志记录器

    用法:
        from chaoxing_sign.logging_config import get_logger
        log = get_logger(__name__)
        # 或者直接给名字:
        log = get_logger("my_module")
    """
    if not _logger_initialized:
        from .config import config as _cfg
        init_logging(_cfg)
    # 确保在 chaoxing_sign 命名空间下，使其继承 handler
    if not name.startswith("chaoxing_sign"):
        name = f"chaoxing_sign.{name}"
    return logging.getLogger(name)
