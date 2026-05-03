"""FastAPI 依赖注入"""
from __future__ import annotations
import json
from pathlib import Path

from fastapi import HTTPException, Query

from .. import database as db_module
from ..auth.session import SessionManager
from ..utils.crypto import decrypt_hybrid
from ..logging_config import get_logger

log = get_logger(__name__)

# 全局 session 管理器（在 app.py 的 lifespan 中初始时可用）
session_manager: SessionManager | None = None

# RSA 私钥缓存
_private_key_pem: str | None = None


def _get_private_key() -> str:
    """加载 RSA 私钥（带缓存）"""
    global _private_key_pem
    if _private_key_pem is not None:
        return _private_key_pem
    from ..config import config as cfg

    private_path = cfg.get("rsa_private_key_path", "rsa_key.pem")
    pub_path = cfg.get("rsa_public_key_path", "rsa_key.pub.pem")
    from ..utils.crypto import _ensure_keys_exist

    _private_key_pem, _ = _ensure_keys_exist(private_path, pub_path)
    return _private_key_pem


def get_public_key_pem() -> str:
    """获取 RSA 公钥 PEM（供 /api/public-key 使用）"""
    from ..config import config as cfg

    private_path = cfg.get("rsa_private_key_path", "rsa_key.pem")
    pub_path = cfg.get("rsa_public_key_path", "rsa_key.pub.pem")
    from ..utils.crypto import _ensure_keys_exist

    _, public_pem = _ensure_keys_exist(private_path, pub_path)
    return public_pem


def decrypt_query_payload(encrypted: str | None = Query(None)) -> dict | None:
    """解密查询参数中的 encrypted 字段，返回原始参数字典。
    若未提供 encrypted 参数则返回 None。
    """
    if not encrypted:
        return None
    try:
        private_key = _get_private_key()
        return decrypt_hybrid(encrypted, private_key)
    except Exception as e:
        log.warning("参数解密失败: %s", e)
        raise HTTPException(400, f"参数解密失败: {e}")


def decrypt_body_payload(body: dict) -> dict | None:
    """解密 JSON body 中的 encrypted 字段，返回原始数据字典。
    若 body 中无 encrypted 字段则返回 None。
    """
    encrypted = body.get("encrypted", "") if body else ""
    if not encrypted:
        return None
    try:
        private_key = _get_private_key()
        return decrypt_hybrid(encrypted, private_key)
    except Exception as e:
        log.warning("Body 解密失败: %s", e)
        raise HTTPException(400, f"参数解密失败: {e}")


def get_client(token: str = Query(...)):
    """从 session 池获取已登录的 ChaoxingClient"""
    if session_manager is None:
        raise HTTPException(503, "服务未就绪")
    return session_manager.get(token)


def require_db():
    if db_module.engine is None:
        raise HTTPException(503, "数据库服务不可用，请稍后重试")


def get_db():
    return db_module.get_db()
