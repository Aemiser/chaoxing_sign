"""Session 管理 — token → ChaoxingClient 池 + TTL 自动清理"""
from __future__ import annotations
import time
from typing import TYPE_CHECKING

from fastapi import HTTPException

from ..logging_config import get_logger

if TYPE_CHECKING:
    from ..client import ChaoxingClient

log = get_logger(__name__)

SESSION_TTL_SECONDS = 24 * 3600


class SessionManager:
    """管理超星客户端会话池，支持 TTL 过期自动清理"""

    def __init__(self):
        self._sessions: dict[str, "ChaoxingClient"] = {}
        self._last_access: dict[str, float] = {}

    def add(self, token: str, client: "ChaoxingClient"):
        self._sessions[token] = client
        self._last_access[token] = time.time()

    def get(self, token: str) -> "ChaoxingClient":
        if token not in self._sessions:
            raise HTTPException(401, "未登录或 session 已过期")
        self._last_access[token] = time.time()
        self._cleanup_expired()
        return self._sessions[token]

    def remove(self, token: str):
        self._sessions.pop(token, None)
        self._last_access.pop(token, None)

    def _cleanup_expired(self):
        now = time.time()
        expired = [
            t for t, ts in self._last_access.items()
            if now - ts > SESSION_TTL_SECONDS
        ]
        for t in expired:
            self._sessions.pop(t, None)
            self._last_access.pop(t, None)
        if expired:
            log.info("清理了 %d 个过期 session", len(expired))

    def __len__(self) -> int:
        return len(self._sessions)
