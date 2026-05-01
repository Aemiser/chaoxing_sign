"""HTTP / Cookie 工具"""
from __future__ import annotations


def generate_course_data(cookie_str: str) -> dict:
    """从 cookie 字符串中提取 key=value 字典"""
    info = {}
    for item in cookie_str.split(";"):
        item = item.strip()
        if "=" in item:
            key, val = item.split("=", 1)
            info[key] = val
    return info
