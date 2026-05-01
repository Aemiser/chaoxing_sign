"""加密工具"""
from __future__ import annotations


def hash_password(password: str, salt: str) -> str:
    """密码加密 — 超星使用明文传输，预留接口"""
    return password
