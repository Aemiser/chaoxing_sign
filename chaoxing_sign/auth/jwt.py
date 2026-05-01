"""JWT 认证工具"""
import logging
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Header, HTTPException

from ..config import config as _cfg

log = logging.getLogger(__name__)

DEFAULT_SECRET = "default-secret-change-in-production"
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

_secret: str | None = None


def _get_secret() -> str:
    """惰性获取 JWT 签名密钥（env > .env 文件 > 自动生成随机密钥）"""
    global _secret
    if _secret is not None:
        return _secret

    configured = _cfg.get("jwt_secret", "")
    if configured and configured != DEFAULT_SECRET:
        _secret = configured
    else:
        _secret = secrets.token_hex(32)
        if not configured:
            log.warning("未找到 .env 配置，JWT 使用随机密钥，重启后所有 token 失效！")
        else:
            log.warning(
                ".env 中 jwt_secret 未配置或仍为示例值，已生成随机密钥。"
                "服务重启后所有用户需重新登录。请尽快设置 jwt_secret。"
            )

    return _secret


def create_jwt(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, _get_secret(), algorithm=ALGORITHM)


def get_current_user_id(authorization: str = Header(...)) -> int:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "无效的认证头")
    token = authorization[7:].strip()
    try:
        payload = jwt.decode(token, _get_secret(), algorithms=[ALGORITHM])
        return int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "登录已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "无效的认证令牌")
