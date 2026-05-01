"""工具函数包

按职责拆分为子模块，此处 re-export 以保持向后兼容：
    from chaoxing_sign.utils import extract_enc_from_qr  # 仍然有效
"""
from .captcha import solve_captcha
from .crypto import hash_password
from .geo import reverse_geocode, reverse_geocode_amap
from .http import generate_course_data
from .json_utils import safe_json_loads
from .parser import parse_course_id_from_url, parse_active_id_from_url, extract_enc_from_qr

__all__ = [
    "hash_password",
    "generate_course_data",
    "parse_course_id_from_url",
    "parse_active_id_from_url",
    "extract_enc_from_qr",
    "reverse_geocode",
    "reverse_geocode_amap",
    "safe_json_loads",
    "solve_captcha",
]
