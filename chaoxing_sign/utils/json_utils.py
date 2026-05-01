"""JSON 工具"""
from __future__ import annotations
import json


def safe_json_loads(text: str) -> dict:
    """安全的 JSON 解析，失败返回 {}"""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}
