"""超星学习通签到 Python 库"""
from .logging_config import init_logging, get_logger
from .config import config

# 模块导入时即初始化日志系统（幂等）
init_logging(config)

from .client import ChaoxingClient
from .types import Course, SignTask, SignType, AccountInfo
from .utils.captcha import solve_captcha

__all__ = [
    "ChaoxingClient", "Course", "SignTask", "SignType", "AccountInfo",
    "get_logger", "solve_captcha",
]
