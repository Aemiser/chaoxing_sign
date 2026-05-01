"""认证模块 — JWT 签发/验证 + Session 管理"""
from .jwt import create_jwt, get_current_user_id, _get_secret, ALGORITHM
import jwt as _jwt

# 向后兼容：test_auth.py 通过包直接访问 _secret（字符串）和 jwt 模块
_secret = _get_secret()
jwt = _jwt

__all__ = ["create_jwt", "get_current_user_id"]
