"""地理编码工具 — 逆地理编码（OSM / 高德）"""
from __future__ import annotations
from typing import Any

import requests

from ..config import config
from ..logging_config import get_logger

log = get_logger(__name__)


def reverse_geocode(lat: float, lon: float, *,
                    lang: str = "zh",
                    timeout: float = 10) -> dict[str, Any]:
    """根据经纬度获取具体位置信息（OpenStreetMap Nominatim）

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
        log.warning("OSM 逆地理编码失败 (%.6f, %.6f): %s", lat, lon, e)
        return {"error": str(e), "lat": lat, "lon": lon}


def reverse_geocode_amap(lat: float, lon: float, *,
                         key: str | None = None,
                         timeout: float = 10) -> dict[str, Any]:
    """根据经纬度获取具体位置信息（高德逆地理编码）

    需要高德 Web API Key：https://console.amap.com

    参数
    ----
    lat : 纬度（度）
    lon : 经度（度）
    key : 高德 Web 服务 API Key，默认从全局 config 取
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
    api_key = key or config.get("amap_key_info", "")
    url = "https://restapi.amap.com/v3/geocode/regeo"
    params = {
        "key": api_key,
        "location": f"{lon},{lat}",
        "extensions": "base",
        "output": "JSON",
    }
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        log.warning("高德逆地理编码失败 (%.6f, %.6f): %s", lat, lon, e)
        return {"error": str(e), "lat": lat, "lon": lon}

    if data.get("status") != "1":
        log.warning("高德逆地理编码返回错误: %s", data.get("info", "未知错误"))
        return {"error": data.get("info", "未知错误"), "lat": lat, "lon": lon}

    regeo = data.get("regeocode", {})
    addr = regeo.get("addressComponent", {})

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
