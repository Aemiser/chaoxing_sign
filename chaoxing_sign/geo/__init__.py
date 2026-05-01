"""几何计算模块 — 三角定位、球面距离、定位缓存"""
from .cache import load_location_cache, save_location_cache

__all__ = ["load_location_cache", "save_location_cache"]
