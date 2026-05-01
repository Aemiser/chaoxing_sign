"""
超星学习通滑块验证码自动化破解脚本
基于 load.min.js 逆向分析，所有加密参数均为标准 MD5
"""

import hashlib
import json
import random
import re
import time
from typing import Optional

import ddddocr
import requests

from chaoxing_sign import ChaoxingClient

# ============================================================
# 常量
# ============================================================

CAPTCHA_ID = "Qt9FIw9o4pwRjOyqM6yizZBh682qN2TU"
CAPTCHA_DOMAIN = "https://captcha.chaoxing.com"
VERSION = "1.1.20"
RUN_ENV = 10  # WEB=10, ANDROID=20, IOS=30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 "
        "Mobile Safari/537.36 ChaoXingStudy_3_6.0.2_android_300"
    ),
}


# ============================================================
# UUID 生成（还原自 JS 源码 _0x11dbad 函数）
# ============================================================

def generate_uuid() -> str:
    """生成符合超星验证码规范的 UUID"""
    hex_chars = "0123456789abcdef"
    arr = [random.choice(hex_chars) for _ in range(36)]
    arr[14] = "4"
    arr[19] = hex_chars[(int(arr[19], 16) & 3) | 8]
    for pos in (8, 13, 18, 23):
        arr[pos] = "-"
    return "".join(arr)


# ============================================================
# 加密函数
# ============================================================

def md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()

def generate_params(service_time: str) -> dict:
    """
    根据服务端时间戳生成三个动态加密参数。
    返回: {captchaKey, token, iv}
    """
    now_ts = str(int(time.time() * 1000))
    print(f"  请求时间戳: {now_ts}")
    uid = generate_uuid()

    captcha_key = md5(service_time + uid)
    token = md5(service_time + CAPTCHA_ID + "slide" + captcha_key)
    token = token + ":" + str(int(service_time) + 300000)
    iv = md5(CAPTCHA_ID + "slide" + now_ts + uid)

    return {
        "captchaKey": captcha_key,
        "token": token,
        "iv": iv,
    }


# ============================================================
# API 请求
# ============================================================

class CaptchaSolver:
    """超星滑块验证码破解器 — 遵循 captcha.chaoxing.com JSONP 协议"""

    def __init__(self, referer: str = "", session: requests.Session = None):
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)
        self.referer = referer

    def _jsonp_url(self, path: str, params: dict) -> str:
        params["callback"] = "cx_captcha_function"
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{CAPTCHA_DOMAIN}/{path}?{query}"

    # ---- 获取服务端时间 ----

    def _get_service_time(self) -> str:
        params = {"captchaId": CAPTCHA_ID, "_": str(int(time.time() * 1000))}
        url = self._jsonp_url("captcha/get/conf", params)
        resp = self.session.get(url, timeout=10)
        m = re.search(r"cx_captcha_function\((.*)\)", resp.text, re.DOTALL)
        if not m:
            raise RuntimeError(f"获取服务端时间失败: {resp.text[:200]}")
        return str(json.loads(m.group(1))["t"])

    # ---- 获取验证码图片（生成加密参数 + 请求图片） ----

    def _get_img_url(self) -> tuple[str, str, str, str]:
        """获取验证码图片 URL 及签名参数。
        Returns (token, shadeImage, cutoutImage, iv)
        """
        service_time = self._get_service_time()
        now_ts = str(int(time.time() * 1000))
        print(f"  请求时间戳: {now_ts}")
        uid = generate_uuid()

        captcha_key = md5(service_time + uid)
        token = md5(service_time + CAPTCHA_ID + "slide" + captcha_key)
        token = token + ":" + str(int(service_time) + 300000)
        iv = md5(CAPTCHA_ID + "slide" + now_ts + uid)

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

        print(f"获取滑块图片成功")
        print(f"  shadeImage: {shade}")
        print(f"  cutoutImage: {cutout}")
        print(f"  请求 token: {token}")
        print(f"  响应 token: {new_token}")
        print(f"  iv: {iv}")
        return token, new_token, shade, cutout, iv

    # ---- 识别滑块距离（带重试） ----

    def distance_x(self):
        for i in range(1, 4):
            req_token, new_token, shadeImage, cutoutImage, iv = self._get_img_url()
            slide = ddddocr.DdddOcr(det=False, ocr=False, show_ad=False)
            big_bytes = client.session.get(shadeImage).content
            small_bytes = client.session.get(cutoutImage).content
            result_x = slide.slide_match(small_bytes, big_bytes, simple_target=True)['target'][0]
            print(f"  ddddocr 识别: {result_x}")
            # 用请求 token（带 :expiry 后缀）验证；响应 token 备用
            return result_x, req_token, iv


    # ---- 提交验证 ----

    def submit_verify(self, distance: int, image_token: str, iv: str) -> str:
        """提交滑块数据，返回 validate 令牌"""
        # distance = input("请手动滑动滑块并点击确定")
        params = {
            'callback': 'cx_captcha_function',
            'captchaId': CAPTCHA_ID,
            'type': 'slide',
            'token': image_token,
            'textClickArr': '[{"x":%s}]'%distance,
            'coordinate': '[]',
            'runEnv': str(RUN_ENV),
            'version': VERSION,
            't': 'a',
            'iv': iv,
            '_': str(int(time.time() * 1000)),
        }
        print(f"提交滑块数据: {params}")

        resp = self.session.get(
            f"{CAPTCHA_DOMAIN}/captcha/check/verification/result",
            params=params, timeout=10,
        )
        m = re.search(r"cx_captcha_function\((.*)\)", resp.text, re.DOTALL)
        if not m:
            print(f"验证提交失败: {resp.text[:200]}")
            return ""

        data = json.loads(m.group(1))
        if data.get("result") is True and data.get("extraData"):
            validate = json.loads(data["extraData"]).get("validate", "")
            print(f"验证成功！validate = {validate}")
            return validate

        print(f"验证失败: {json.dumps(data, ensure_ascii=False)}")
        return ""



    # ---- 一键执行 ----

    def solve(self, interactive: bool = False) -> str:
        """执行完整滑块验证流程，返回 validate 令牌。
        interactive=True: 打印图片 URL，等待手动输入距离或输入空串自动偏移探测。
        """
        for attempt in range(1, 4):
            req_token, new_token, shade, cutout, iv = self._get_img_url()
            slide = ddddocr.DdddOcr(det=False, ocr=False, show_ad=False)
            big = client.session.get(shade).content
            small = client.session.get(cutout).content
            raw = slide.slide_match(small, big, simple_target=True)['target']
            ddddocr_x = raw[0] if isinstance(raw, (list, tuple)) else raw
            print(f"  ddddocr 识别: {ddddocr_x}px (原始: {raw})")

            if interactive:
                print(f"\n  底图: {shade}")
                print(f"  缺口: {cutout}")
                print(f"  ddddocr 参考值: {ddddocr_x}")
                user = input("  输入距离值（空=自动探测±10） → ").strip()
                if user:
                    distance = int(user)
                    result = self.submit_verify(distance, new_token, iv)
                    if result:
                        return result
                    print(f"  失败，请重试或输入其他值")
                    continue
                # 自动探测偏移：ddddocr ± 0,2,4,6,8,10
                for offset in [0, -2, 2, -4, 4, -6, 6, -8, 8, -10, 10]:
                    test_x = ddddocr_x - offset
                    print(f"  尝试 x={test_x} (偏移 {offset:+d})...")
                    result = self.submit_verify(test_x, new_token, iv)
                    if result:
                        print(f"  ★ 命中偏移: {offset:+d}")
                        return result
                print(f"  所有偏移均失败，获取新图片重试...")
                continue
            else:
                result = self.submit_verify(ddddocr_x, new_token, iv)
                if result:
                    return result
            print(f"  第 {attempt} 次失败，重试...")
        return ""


# ============================================================
# 签到请求（可选）
# ============================================================

def sign_in(
    session: requests.Session,
    validate: str,
    active_id: str = "3000158418560",
    course_id: str = "263432266",
    uid: str = "302078632",
    name: str = "",
    fid: str = "0",
    latitude: str = "-1",
    longitude: str = "-1",
    address: str = "",
    device_code: str = "",
    if_ti_jiao: int = 1,
    app_type: str = "15",
    sign_code: str = "1111",
) -> str:
    """
    发送签到请求到 /pptSign/stuSignajax。
    返回服务端响应文本（success / 错误提示）。
    """
    from urllib.parse import urlencode

    params = {
        "name": name,
        "signCode":sign_code,
        "address": address,
        "activeId": active_id,
        "courseId": course_id,
        "uid": uid,
        "clientip": "",
        "latitude": latitude,
        "longitude": longitude,
        "fid": fid,
        "appType": app_type,
        "ifTiJiao": if_ti_jiao,
        "validate": validate,
        "deviceCode": device_code,
        "vpProbability": "",
        "vpStrategy": "",
        "currentFaceId": "",
        "ifCFP": "0",
    }

    resp = session.get(
        "https://mobilelearn.chaoxing.com/pptSign/stuSignajax",
        params=params,
        timeout=15,
    )

    print(f"签到响应: {resp.text}")
    return resp.text


# ============================================================
# 主程序
# ============================================================

if __name__ == "__main__":
    client = ChaoxingClient()
    if not client.login("13043459114", "13043459114a"):
        print("登录失败")
    # 步骤 1-4: 破解滑块验证码
    solver = CaptchaSolver(
        referer="https://mobilelearn.chaoxing.com/pptSign/stuSignajax",
        session=client.session,
    )
    validate = solver.solve(interactive=True)

    if validate:
        print(f"\n拿到 validate 令牌: {validate}")
        print("可将其传入 sign_in() 函数完成签到")

        # 如果需要直接签到，取消下面的注释:
        result = sign_in(
            validate=validate,
            active_id="3000158418560",
            course_id="263432266",
            uid="302078632",
            name="你的名字",
            # latitude="39.915119",
            # longitude="116.403963",
            # address="北京市海淀区中关村大街XX号",
            sign_code="1111",
        )
    else:
        print("验证失败，请检查参数或重试")
