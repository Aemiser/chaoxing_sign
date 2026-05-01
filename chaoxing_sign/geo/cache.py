"""三角定位缓存 — 活动ID → 成功坐标"""
from __future__ import annotations
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

LOCATION_CACHE_PATH = Path(__file__).parent.parent.parent / "location_cache.json"


def load_location_cache() -> dict[str, tuple[float, float]]:
    try:
        if LOCATION_CACHE_PATH.exists():
            raw = json.loads(LOCATION_CACHE_PATH.read_text(encoding="utf-8"))
            return {k: (float(v[0]), float(v[1])) for k, v in raw.items()}
    except Exception:
        pass
    return {}


def save_location_cache(cache: dict[str, tuple[float, float]]):
    try:
        data = {k: [v[0], v[1]] for k, v in cache.items()}
        LOCATION_CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        log.warning("保存定位缓存失败: %s", e)
