"""签到执行器 — 各类型签到策略 + 指定位置三角定位求解"""
from __future__ import annotations
import re
import json
import math
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from .constants import PRESIGN_URL, STUSIGN_URL, EARTH_RADIUS
from ..types import SignTask, SignType
from ..utils import safe_json_loads, reverse_geocode_amap, extract_enc_from_qr
from ..trilateration import solve_gn, _haversine
from ..geo.cache import load_location_cache, save_location_cache
from ..logging_config import get_logger

if TYPE_CHECKING:
    from ..client import ChaoxingClient

log = get_logger(__name__)


def _apply_location_offset(lat: float, lon: float) -> tuple[float, float]:
    """应用配置中的坐标偏移修正（WGS-84 → Chaoxing 坐标系）"""
    from ..config import config as cfg

    offset_e = cfg.get("location_offset", {}).get("east", 0.0)
    offset_n = cfg.get("location_offset", {}).get("north", 0.0)

    log.info(f"坐标偏移修正：东 {offset_e} 米，北 {offset_n} 米")
    if offset_e == 0.0 and offset_n == 0.0:
        return lat, lon

    cos_lat = math.cos(math.radians(lat))
    new_lat = lat + math.degrees(offset_n / EARTH_RADIUS)
    new_lon = lon + math.degrees(offset_e / (EARTH_RADIUS * cos_lat))
    return new_lat, new_lon

PROBE_POINTS = [
    ("哈尔滨",  45.75, 126.63),
    ("乌鲁木齐", 43.83, 87.62),
    ("三亚",    18.25, 109.50),
    ("拉萨",    29.66, 91.12),
    ("上海",    31.23, 121.47),
]

MAX_GRADIENT_ROUNDS = 25


class SignExecutor:
    """签到执行器 — 封装所有签到类型的业务逻辑

    从 ChaoxingClient 中拆分出来，通过构造器注入 client 引用。
    """

    def __init__(self, client: "ChaoxingClient"):
        self._client = client

    # ── dispatch ──────────────────────────────────────────────

    def execute(self, task: SignTask, **kwargs) -> "tuple[bool, str]":
        sign_methods = {
            SignType.NORMAL: self._sign_normal,
            SignType.PHOTO: self._sign_photo,
            SignType.GESTURE: self._sign_gesture,
            SignType.LOCATION: self._sign_location,
            SignType.QRCODE: self._sign_qrcode,
            SignType.QRCODE_LOCATION: self._sign_qrcode_location,
            SignType.CODE: self._sign_code,
        }
        method = sign_methods.get(task.sign_type, self._sign_normal)
        return method(task, **kwargs)

    def execute_with_uid(self, task: SignTask, target_uid: str, **kwargs) -> "tuple[bool, str]":
        """为指定 uid 执行签到（代签核心方法）"""
        params = self._client._base_params(task)
        params["uid"] = target_uid
        if kwargs.get("enc"):
            params["enc"] = kwargs["enc"]
        if kwargs.get("longitude"):
            params["longitude"] = kwargs["longitude"]
            params["latitude"] = kwargs.get("latitude", "-1")
        return self._client._do_sign_get(task, params)

    # ── 普通 / 拍照 / 手势 / 签到码 ─────────────────────────

    def _sign_normal(self, task: SignTask, **kwargs) -> "tuple[bool, str]":
        return self._client._do_sign_get(task, self._client._base_params(task))

    def _sign_photo(self, task: SignTask, **kwargs) -> "tuple[bool, str]":
        return self._sign_normal(task, **kwargs)

    def _sign_gesture(self, task: SignTask, **kwargs) -> "tuple[bool, str]":
        gesture = kwargs.get("gesture", "")
        params = self._client._base_params(task)
        if gesture:
            params["signCode"] = gesture
        return self._client._do_sign_get(task, params)

    def _sign_code(self, task: SignTask, **kwargs) -> "tuple[bool, str]":
        code = kwargs.get("code", "")
        params = self._client._base_params(task)
        if code:
            params["signCode"] = code
        return self._client._do_sign_get(task, params)

    # ── 二维码签到 ──────────────────────────────────────────

    def _sign_qrcode(self, task: SignTask, **kwargs) -> "tuple[bool, str]":
        enc = kwargs.get("enc", task.enc or "")
        if not enc:
            qr_content = kwargs.get("qr_content", "")
            if qr_content:
                enc = extract_enc_from_qr(qr_content)
        if not enc:
            log.error("二维码签到缺少 enc 参数")
            return (False, "二维码签到缺少 enc 参数")
        params = self._client._base_params(task)
        params["enc"] = enc
        return self._client._do_sign_get(task, params)

    def _sign_qrcode_location(self, task: SignTask, **kwargs) -> "tuple[bool, str]":
        enc = kwargs.get("enc", task.enc or "")
        if not enc:
            qr_content = kwargs.get("qr_content", "")
            if qr_content:
                enc = extract_enc_from_qr(qr_content)
        if not enc:
            log.error("指定位置二维码签到缺少 enc 参数")
            return (False, "指定位置二维码签到缺少 enc 参数")

        lng = float(kwargs.get("longitude", task.location_longitude or "116.404"))
        lat = float(kwargs.get("latitude", task.location_latitude or "39.915"))
        lat, lng = _apply_location_offset(lat, lng)
        location_name = kwargs.get("location_name", task.location_name or "")

        try:
            geo = reverse_geocode_amap(lat, lng)
            address = geo.get("display_name", location_name) if geo else location_name
        except Exception:
            address = location_name

        location_json = json.dumps({
            "result": 1,
            "address": address or "",
            "longitude": lng,
            "latitude": lat,
        }, ensure_ascii=False)

        params = self._client._base_params(task)
        params["enc"] = enc
        params["location"] = location_json
        return self._client._do_sign_get(task, params)

    # ── 位置签到 ────────────────────────────────────────────

    def _sign_location(self, task: SignTask, **kwargs) -> "tuple[bool, str]":
        # 前端可关闭三角定位：直接提交选中坐标，跳过指定地点求解
        use_trilateration = kwargs.pop("use_trilateration", "1")
        if use_trilateration != "0" and self._check_location_type(task) == "named":
            return self._solve_named_location(task, **kwargs)

        lng = kwargs.get("longitude", task.location_longitude or "116.404")
        lat = kwargs.get("latitude", task.location_latitude or "39.915")
        log.info("提交位置：%s, %s" % (lng, lat))
        lat, lng = _apply_location_offset(float(lat), float(lng))
        log.info("提交位置：%s, %s" % (lng, lat))
        params = self._client._base_params(task)
        params["latitude"] = str(lat)
        params["longitude"] = str(lng)
        params["address"] = reverse_geocode_amap(lat, lng).get("display_name", "")
        return self._client._do_sign_get(task, params)

    def _check_location_type(self, task: SignTask) -> str:
        """检查位置签到类型：'normal' 普通位置签到, 'named' 指定地点位置签到"""
        try:
            resp = self._client.session.get(PRESIGN_URL, params={
                "courseId": task.course_id,
                "classId": task.class_id,
                "activePrimaryId": task.active_id,
                "general": "1",
                "sys": "1",
                "ls": "1",
                "appType": "15",
                "uid": self._client._uid,
            }, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")
            el = soup.select_one("#ifopenAddress")
            if el and el.get("value") == "1":
                log.info("检测到指定地点位置签到")
                return "named"
        except Exception as e:
            log.warning("检查位置签到类型失败: %s", e)
        return "normal"

    # ──  ────────────────────────────────────────

    def _probe(self, task: SignTask, lat: float, lon: float) -> tuple[str, float | None]:
        """发送签到请求并解析结果。

        Returns ("success", None), ("distance", meters), or ("error", None)
        """
        from ..utils.captcha import solve_captcha
        # 应用坐标偏移修正
        lat, lon = _apply_location_offset(lat, lon)
        params = self._client._base_params(task)
        params["latitude"] = str(lat)
        params["longitude"] = str(lon)
        params["address"] = reverse_geocode_amap(
            float(params["latitude"]), float(params["longitude"])
        ).get("display_name", "")

        validate = solve_captcha(self._client.session, referer=STUSIGN_URL)
        if validate:
            params["validate"] = validate
        try:
            resp = self._client.session.get(STUSIGN_URL, params=params, timeout=15)
            text = resp.text.strip()
        except Exception as e:
            log.error("探测请求失败 (%.6f, %.6f): %s", lat, lon, e)
            return ("error", None)

        if text == "success" or "成功" in text or "重复" in text or "已签到" in text:
            log.info("探测 (%.6f,%.6f) → 签到成功", lon, lat)
            return ("success", None)

        m = re.search(r"距教师指定签到地点([\d.]+)米", text)
        if m:
            d = float(m.group(1))
            log.info("探测 (%.6f, %.6f) → %.0f 米", lat, lon, d)
            return ("distance", d)

        log.warning("探测返回未知内容: %s", text[:100])
        return ("error", None)

    def _solve_named_location(self, task: SignTask, **kwargs) -> "tuple[bool, str]":
        """指定地点位置签到 — 五探测点 + Gauss-Newton 球面最小二乘求解 + 缓存"""
        # 1. 检查缓存
        cache = load_location_cache()
        cached = cache.get(task.active_id)
        if cached is not None:
            lat, lon = cached
            log.info("命中定位缓存: (%.6f, %.6f)", lat, lon)
            lat, lon = _apply_location_offset(lat, lon)
            params = self._client._base_params(task)
            params["latitude"] = str(lat)
            params["longitude"] = str(lon)
            params["address"] = reverse_geocode_amap(float(lat), float(lon)).get("display_name", "")
            ok, msg = self._client._do_sign_get(task, params)
            if ok:
                return (True, msg)
            log.info("缓存坐标签到失败，重新探测")
            del cache[task.active_id]

        # 2. 探测 5 个点获取距离
        distances = []
        for name, lat, lon in PROBE_POINTS:
            params = self._client._base_params(task)
            params["latitude"] = str(lat)
            params["longitude"] = str(lon)
            try:
                resp = self._client.session.get(STUSIGN_URL, params=params, timeout=15)
                text = resp.text.strip()
            except Exception as e:
                log.error("探测请求失败 (%s): %s", name, e)
                continue

            if text == "success":
                log.info("探测点 %s 已在签到范围内，直接签到成功", name)
                return (True, "签到成功")
            if "成功" in text or "重复" in text or "已签到" in text:
                log.info("探测点 %s 签到结果: %s", name, text[:80])
                return (True, "签到成功")

            m = re.search(r"距教师指定签到地点([\d.]+)米", text)
            if m:
                d = float(m.group(1))
                distances.append((lat, lon, d))
                log.info("探测点 %s: 距离目标 %.1f 米", name, d)
            else:
                log.warning("探测点 %s 未返回距离信息: %s", name, text[:100])

        if len(distances) < 3:
            log.error("有效探测点不足 3 个（共 %d 个），无法三角定位", len(distances))
            return (False, f"有效探测点不足3个（共{len(distances)}个），无法三角定位")

        # 3. 初始猜测 = C(5,3) 组合平面定位均值
        from itertools import combinations
        from ..trilateration import solve_three

        guesses = set()
        for (la1, lo1, d1), (la2, lo2, d2), (la3, lo3, d3) in combinations(distances, 3):
            r = solve_three(la1, lo1, d1, la2, lo2, d2, la3, lo3, d3)
            if r is not None:
                guesses.add(r)

        if not guesses:
            log.error("所有组合均无解")
            return (False, "所有探测点组合均无解，无法定位目标位置")

        guess_lat = sum(g[0] for g in guesses) / len(guesses)
        guess_lon = sum(g[1] for g in guesses) / len(guesses)
        log.info("初始猜测 (%d 组平均): (%.6f, %.6f)", len(guesses), guess_lat, guess_lon)

        # 4. Gauss-Newton 球面精修
        target_lat, target_lon = solve_gn(distances, guess_lat, guess_lon)
        log.info("GN 初始解: (%.6f, %.6f)", target_lat, target_lon)

        # 5. 有限差分梯度下降
        def _gradient_descent(lat: float, lon: float) -> tuple[bool, float, float]:
            for round_num in range(MAX_GRADIENT_ROUNDS):
                status, val = self._probe(task, lat, lon)
                if status == "success":
                    cache[task.active_id] = (lat, lon)
                    save_location_cache(cache)
                    return (True, lat, lon)
                if status != "distance":
                    return (False, lat, lon)

                d_center = val

                # 较大的探测步长以克服 API 距离舍入误差
                delta_m = max(150.0, min(600.0, d_center * 0.35))
                delta_deg = delta_m / EARTH_RADIUS
                cos_tlat = math.cos(math.radians(lat))

                e_lat, e_lon = lat, lon + math.degrees(delta_deg / cos_tlat)
                status, val = self._probe(task, e_lat, e_lon)
                if status == "success":
                    cache[task.active_id] = (lat, lon)
                    save_location_cache(cache)
                    return (True, lat, lon)
                d_east = val if status == "distance" else d_center

                n_lat, n_lon = lat + math.degrees(delta_deg), lon
                status, val = self._probe(task, n_lat, n_lon)
                if status == "success":
                    cache[task.active_id] = (lat, lon)
                    save_location_cache(cache)
                    return (True, lat, lon)
                d_north = val if status == "distance" else d_center

                grad_e = (d_center - d_east) / delta_m
                grad_n = (d_center - d_north) / delta_m

                grad_mag2 = grad_e * grad_e + grad_n * grad_n
                if grad_mag2 < 1e-15:
                    log.warning("梯度为零，无法继续")
                    return (False, lat, lon)

                scale = d_center / grad_mag2
                move_e = scale * grad_e
                move_n = scale * grad_n

                orig_lat = lat
                lat += math.degrees(move_n / EARTH_RADIUS)
                lon += math.degrees(move_e / (EARTH_RADIUS * math.cos(math.radians(orig_lat))))

                log.info("第 %d 轮: dist=%.0fm Δe=%.0fm Δn=%.0fm → (%.6f, %.6f)",
                         round_num + 1, d_center, move_e, move_n, lat, lon)

            return (False, lat, lon)

        ok, final_lat, final_lon = _gradient_descent(target_lat, target_lon)
        if ok:
            return (True, "签到成功")

        # 6. 主初始解未收敛 → 尝试备选初始猜测
        log.info("主初始解未收敛，尝试备选初始点...")
        alt_guesses = []
        for (la1, lo1, d1), (la2, lo2, d2), (la3, lo3, d3) in combinations(distances, 3):
            r = solve_three(la1, lo1, d1, la2, lo2, d2, la3, lo3, d3)
            if r is not None and r not in [g for g in alt_guesses]:
                alt_guesses.append(r)
            if len(alt_guesses) >= 5:
                break

        for alt_lat, alt_lon in alt_guesses:
            # 排除已尝试过的主解（1km 内视为重复）
            d_between = _haversine(alt_lat, alt_lon, final_lat, final_lon)
            if d_between < 1000:
                continue
            log.info("尝试备选初始点: (%.6f, %.6f)", alt_lat, alt_lon)
            ok, alt_final_lat, alt_final_lon = _gradient_descent(alt_lat, alt_lon)
            if ok:
                return (True, "签到成功")

        log.error("所有初始解均未收敛，签到失败")
        return (False, f"无法收敛到目标位置（已尝试{len(alt_guesses)+1}个初始点）")
