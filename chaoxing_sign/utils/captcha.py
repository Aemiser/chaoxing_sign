"""超星滑块验证码破解工具。

用法:
    from chaoxing_sign.utils import solve_captcha
    from chaoxing_sign import ChaoxingClient

    client = ChaoxingClient()
    client.login("手机号", "密码")
    validate = solve_captcha(client.session)
    # 将 validate 传入签到请求
"""

import hashlib
import json
import random
import re
import time

import cv2
import numpy as np
import requests

# ============================================================
# 常量
# ============================================================

CAPTCHA_ID = "Qt9FIw9o4pwRjOyqM6yizZBh682qN2TU"
CAPTCHA_DOMAIN = "https://captcha.chaoxing.com"
VERSION = "1.1.20"
RUN_ENV = 10  # WEB=10, ANDROID=20, IOS=30


# ============================================================
# 工具函数
# ============================================================

def _md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def _generate_uuid() -> str:
    hex_chars = "0123456789abcdef"
    arr = [random.choice(hex_chars) for _ in range(36)]
    arr[14] = "4"
    arr[19] = hex_chars[(int(arr[19], 16) & 3) | 8]
    for pos in (8, 13, 18, 23):
        arr[pos] = "-"
    return "".join(arr)


# ============================================================
# 内部实现
# ============================================================

class _CaptchaSolver:
    """超星滑块验证码破解器 — 遵循 captcha.chaoxing.com JSONP 协议"""

    def __init__(self, session: requests.Session, referer: str = ""):
        self.session = session
        self.referer = referer

    def _jsonp_url(self, path: str, params: dict) -> str:
        params["callback"] = "cx_captcha_function"
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{CAPTCHA_DOMAIN}/{path}?{query}"

    def _get_service_time(self) -> str:
        params = {"captchaId": CAPTCHA_ID, "_": str(int(time.time() * 1000))}
        url = self._jsonp_url("captcha/get/conf", params)
        resp = self.session.get(url, timeout=10)
        m = re.search(r"cx_captcha_function\((.*)\)", resp.text, re.DOTALL)
        if not m:
            raise RuntimeError(f"获取服务端时间失败: {resp.text[:200]}")
        return str(json.loads(m.group(1))["t"])

    def _get_img_url(self) -> tuple[str, str, str, str, str]:
        service_time = self._get_service_time()
        now_ts = str(int(time.time() * 1000))
        uid = _generate_uuid()

        captcha_key = _md5(service_time + uid)
        token = _md5(service_time + CAPTCHA_ID + "slide" + captcha_key)
        token = token + ":" + str(int(service_time) + 300000)
        iv = _md5(CAPTCHA_ID + "slide" + now_ts + uid)

        req_params = {
            "captchaId": CAPTCHA_ID, "type": "slide", "version": VERSION,
            "captchaKey": captcha_key, "token": token,
            "referer": self.referer, "iv": iv,
            "_": now_ts,
        }
        url = self._jsonp_url("captcha/get/verification/image", req_params)
        resp = self.session.get(url, timeout=15)
        m = re.search(r"cx_captcha_function\((.*)\)", resp.text, re.DOTALL)
        if not m:
            raise RuntimeError(f"获取图片失败: {resp.text[:200]}")

        data = json.loads(m.group(1))
        vo = data.get("imageVerificationVo", {})
        shade = vo.get("shadeImage", "") or data.get("shadeImage", "")
        cutout = vo.get("cutoutImage", "") or data.get("cutoutImage", "")
        new_token = data.get("token", token)

        return token, new_token, shade, cutout, iv

    def _find_gap(self, shade_url: str, cutout_url: str) -> int:
        big_bytes = self.session.get(shade_url).content
        small_bytes = self.session.get(cutout_url).content

        big = cv2.imdecode(np.frombuffer(big_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
        small_raw = cv2.imdecode(np.frombuffer(small_bytes, np.uint8), cv2.IMREAD_UNCHANGED)
        if big is None or small_raw is None:
            return 0

        if small_raw.shape[-1] == 4:
            opaque = small_raw[:, :, 3] > 128
        else:
            opaque = np.ones(small_raw.shape[:2], dtype=bool)

        ys, xs = np.where(opaque)
        if len(xs) == 0:
            return 0
        ox_min, ox_max = int(xs.min()), int(xs.max())
        oy_min, oy_max = int(ys.min()), int(ys.max())
        offset_x = ox_min

        small_gray = cv2.imdecode(np.frombuffer(small_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
        if small_gray is None:
            small_gray = cv2.cvtColor(small_raw[:, :, :3], cv2.COLOR_BGR2GRAY)
        template = small_gray[oy_min:oy_max + 1, ox_min:ox_max + 1]

        result = cv2.matchTemplate(big, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        tm_x = int(max_loc[0])
        distance = tm_x - offset_x
        return max(0, distance)

    def _submit_verify(self, distance: int, image_token: str, iv: str) -> str:
        distance = int(distance)
        params = {
            "callback": "cx_captcha_function",
            "captchaId": CAPTCHA_ID,
            "type": "slide",
            "token": image_token,
            "textClickArr": json.dumps([{"x": distance}], separators=(",", ":")),
            "coordinate": "[]",
            "runEnv": str(RUN_ENV),
            "version": VERSION,
            "t": "a",
            "iv": iv,
            "_": str(int(time.time() * 1000)),
        }
        headers = {}
        if self.referer:
            headers["Referer"] = self.referer
        resp = self.session.get(
            f"{CAPTCHA_DOMAIN}/captcha/check/verification/result",
            params=params, timeout=10, headers=headers,
        )
        m = re.search(r"cx_captcha_function\((.*)\)", resp.text, re.DOTALL)
        if not m:
            return ""

        data = json.loads(m.group(1))
        if data.get("result") is True and data.get("extraData"):
            return json.loads(data["extraData"]).get("validate", "")
        return ""

    def solve(self) -> str:
        """执行完整滑块验证流程，返回 validate 令牌。"""
        for _ in range(3):
            _, new_token, shade, cutout, iv = self._get_img_url()
            distance = self._find_gap(shade, cutout)
            if distance <= 0:
                continue
            validate = self._submit_verify(distance, new_token, iv)
            if validate:
                return validate
        return ""


# ============================================================
# 公开接口
# ============================================================

def solve_captcha(session: requests.Session, referer: str = "") -> str:
    """破解一次超星滑块验证码，返回 validate 令牌。

    Args:
        session: 已登录的 requests.Session（如 client.session）
        referer: 触发验证码的页面 URL（可选，用于 Referer 请求头）

    Returns:
        validate 令牌字符串

    Raises:
        RuntimeError: 连续 3 次破解失败
    """
    solver = _CaptchaSolver(session=session, referer=referer)
    validate = solver.solve()
    if not validate:
        raise RuntimeError("验证码破解失败：连续 3 次未通过验证")
    return validate
