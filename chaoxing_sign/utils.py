"""工具函数 - 加密、编码等"""
from __future__ import annotations
import base64
import hashlib
import re
import json
from typing import Optional, Any
from config import config
import requests


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


def reverse_geocode(lat: float, lon: float, *,
                    lang: str = "zh",
                    timeout: float = 10) -> dict[str, Any]:
    """根据经纬度获取具体位置信息（逆地理编码）

    使用 OpenStreetMap Nominatim 免费 API。

    参数
    ----
    lat : 纬度（度）
    lon : 经度（度）
    lang : 返回语言，默认 "zh" 中文
    timeout : 请求超时秒数

    返回
    ----
    dict 包含:
        display_name : 完整地址描述
        address      : 结构化地址 dict（国家/省/市/区/街道等）
        lat, lon     : 实际匹配经纬度
        error        : 仅在请求失败时存在
    """
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        "lat": lat,
        "lon": lon,
        "format": "json",
        "accept-language": lang,
        "zoom": 18,
    }
    headers = {
        "User-Agent": "ChaoxingSignPython/1.0",
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            return {"error": data["error"], "lat": lat, "lon": lon}
        return {
            "display_name": data.get("display_name", ""),
            "address": data.get("address", {}),
            "lat": float(data.get("lat", lat)),
            "lon": float(data.get("lon", lon)),
        }
    except requests.RequestException as e:
        return {"error": str(e), "lat": lat, "lon": lon}


def reverse_geocode_amap(lat: float, lon: float, *,
                         timeout: float = 10) -> dict[str, Any]:
    """根据经纬度获取具体位置信息（高德逆地理编码）

    需要高德 Web API Key：https://console.amap.com

    参数
    ----
    lat : 纬度（度）
    lon : 经度（度）
    key : 高德 Web 服务 API Key
    timeout : 请求超时秒数

    返回
    ----
    dict 包含:
        display_name : 完整地址描述
        address      : 结构化地址 dict（国家/省/市/区/街道等）
        adcode       : 行政区划编码
        lat, lon     : 经纬度
        error        : 仅在请求失败时存在
    """
    url = "https://restapi.amap.com/v3/geocode/regeo"
    params = {
        "key":  config["amap_key_info"],
        "location": f"{lon},{lat}",
        "extensions": "base",
        "output": "JSON",
    }
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        return {"error": str(e), "lat": lat, "lon": lon}

    if data.get("status") != "1":
        return {"error": data.get("info", "未知错误"), "lat": lat, "lon": lon}

    regeo = data.get("regeocode", {})
    addr = regeo.get("addressComponent", {})

    # 高德返回的字段扁平化为结构化 dict
    return {
        "display_name": regeo.get("formatted_address", ""),
        "address": {
            "country":  addr.get("country", ""),
            "province": addr.get("province", ""),
            "city":     addr.get("city", []) or "",
            "district": addr.get("district", ""),
            "township": addr.get("township", ""),
            "street":   addr.get("streetNumber", {}).get("street", ""),
            "number":   addr.get("streetNumber", {}).get("number", ""),
        },
        "adcode": addr.get("adcode", ""),
        "lat": lat,
        "lon": lon,
    }


