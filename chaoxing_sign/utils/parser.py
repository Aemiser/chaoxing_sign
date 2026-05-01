"""URL / QR 解析工具"""
from __future__ import annotations
import re


def parse_course_id_from_url(url: str) -> tuple[str, str]:
    """从 URL 中解析课程 ID 和班级 ID"""
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
    """从 URL 中解析活动 ID"""
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
    """从二维码内容中提取 enc 参数

    统一入口 — 所有模块应通过此函数提取 enc，避免正则重复。
    """
    if "enc=" in content:
        match = re.search(r"enc=([a-zA-Z0-9_\-]+)", content)
        if match:
            return match.group(1)
    return content.strip()
