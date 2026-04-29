"""JWT 认证工具"""
import json
import logging
import secrets
from pathlib import Path
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Header, HTTPException

log = logging.getLogger(__name__)

_config_path = Path(__file__).parent.parent / "config.json"
DEFAULT_SECRET = "default-secret-change-in-production"
_secret = DEFAULT_SECRET
_warned_default_secret = False

if _config_path.exists():
    try:
        cfg = json.loads(_config_path.read_text(encoding="utf-8"))
        configured = cfg.get("jwt_secret", "")
        if configured and configured != DEFAULT_SECRET:
            _secret = configured
        else:
            _secret = secrets.token_hex(32)
            log.warning(
                "config.json 中 jwt_secret 未配置或仍为示例值，已生成随机密钥。"
                "服务重启后所有用户需重新登录。请尽快在 config.json 中设置 jwt_secret。"
            )
    except Exception:
        pass

if _secret == DEFAULT_SECRET:
    log.warning("未找到 config.json，JWT 使用默认密钥，生产环境极不安全！")

ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24


def create_jwt(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, _secret, algorithm=ALGORITHM)


def get_current_user_id(authorization: str = Header(...)) -> int:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "无效的认证头")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, _secret, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "登录已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "无效的认证令牌")
