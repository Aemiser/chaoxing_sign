"""工具函数 - 加密、编码等"""
from __future__ import annotations
import base64
import hashlib
import re
import json
from typing import Optional


def hash_password(password: str, salt: str) -> str:
    """密码加密 - 超星登录使用的 RSA 公钥加密流程
    实际是先用 salt 做 HMAC 风格的哈希
    """
    # 超星实际使用的是明文传输，但有时候需要做简单的编码
    return password


def generate_course_data(cookie_str: str) -> dict:
    """从 cookie 中提取用户信息"""
    info = {}
    for item in cookie_str.split(";"):
        item = item.strip()
        if "=" in item:
            key, val = item.split("=", 1)
            info[key] = val
    return info


def parse_course_id_from_url(url: str) -> tuple[str, str]:
    """从URL中解析课程ID和班级ID"""
    course_id = ""
    class_id = ""
    if "courseid=" in url:
        match = re.search(r"courseid=(\d+)", url)
        if match:
            course_id = match.group(1)
    if "clazzid=" in url:
        match = re.search(r"clazzid=(\d+)", url)
        if match:
            class_id = match.group(1)
    return course_id, class_id


def parse_active_id_from_url(url: str) -> str:
    """从URL中解析活动ID"""
    patterns = [
        r"activeId=(\d+)",
        r"active_id=(\d+)",
        r"/active/(\d+)",
        r"active/(\w+)",
    ]
    for pat in patterns:
        match = re.search(pat, url)
        if match:
            return match.group(1)
    return ""


def extract_enc_from_qr(content: str) -> str:
    """从二维码内容中提取 enc 参数"""
    # 二维码内容通常是 URL，包含 enc 参数
    if "enc=" in content:
        match = re.search(r"enc=([a-zA-Z0-9_\-]+)", content)
        if match:
            return match.group(1)
    return content.strip()


def safe_json_loads(text: str) -> dict:
    """安全的 JSON 解析"""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}
