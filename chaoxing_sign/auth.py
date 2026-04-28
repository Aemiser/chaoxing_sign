"""JWT 认证工具"""
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Header, HTTPException

_config_path = Path(__file__).parent.parent / "config.json"
_secret = "default-secret-change-in-production"

if _config_path.exists():
    try:
        cfg = json.loads(_config_path.read_text(encoding="utf-8"))
        _secret = cfg.get("jwt_secret", _secret)
    except Exception:
        pass

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
