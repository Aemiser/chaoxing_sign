"""核心API客户端 - 登录、课程、活动、签到"""
from __future__ import annotations
import re
import json
import time
import logging
from pathlib import Path
from typing import Optional
import requests
from bs4 import BeautifulSoup

from .types import Course, SignTask, SignType, AccountInfo
from .utils import safe_json_loads

log = logging.getLogger(__name__)

# ============================================================
# API 端点
# ============================================================
PASSPORT_HOST = "https://passport2.chaoxing.com"
MOBILE_API = "https://mobilelearn.chaoxing.com"
MOOC_API = "https://mooc1-api.chaoxing.com"
SSO_API = "https://sso.chaoxing.com"

LOGIN_URL = f"{PASSPORT_HOST}/fanyalogin"
USER_INFO_URL = f"{SSO_API}/apis/login/userLogin4UAP.do"
COURSE_LIST_URL = f"{MOOC_API}/mycourse/backclazzdata"
ACTIVE_TASK_URL = f"{MOBILE_API}/ppt/activeAPI/taskactivelist"

# 签到接口
PRESIGN_URL = f"{MOBILE_API}/newsign/preSign"
STUSIGN_URL = f"{MOBILE_API}/pptSign/stuSignajax"
SIGN_IN_URL = f"{MOBILE_API}/widget/sign/pcStuSignController/signIn"
# 旧版备用
QRCODE_SIGN_URL = f"{MOBILE_API}/ppt/activeAPI/qrcodeSign"
LOCATION_SIGN_URL = f"{MOBILE_API}/ppt/activeAPI/locationSign"

ANDROID_UA = (
    "Dalvik/2.1.0 (Linux; U; Android 13; SM-G981B Build/TP1A.220624.014) "
    "com.chaoxing.mobile/ChaoXingStudy_3.0_48_20231201_android"
)

HEADERS = {
    "User-Agent": ANDROID_UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.8",
    "X-Requested-With": "com.chaoxing.mobile",
}


class ChaoxingClient:
    """超星学习通 API 客户端"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        # 全局默认超时，防止个别请求永久挂起
        adapter = requests.adapters.HTTPAdapter(max_retries=2)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self._uid = ""
        self._name = ""
        self._logged_in = False

    # ================================================================
    # 登录
    # ================================================================

    def login(self, phone: str, password: str, skip_user_info: bool = False) -> bool:
        """手机号 + 密码登录

        skip_user_info: 跳过后置的 SSO uid/name 查询，仅从 cookie 提取 uid，
                        可省一次 HTTP 往返（~500ms）。name 留待 get_account_info() 补充。
        """
        # Step 1: 获取 cookie
        try:
            self.session.get(
                f"{PASSPORT_HOST}/login?newversion=true",
                timeout=10,
                allow_redirects=True,
            )
        except Exception as e:
            log.warning("获取登录页 cookie 失败: %s", e)

        # Step 2: 提交登录
        login_data = {
            "fid": "-1",
            "uname": phone,
            "password": password,
            "refer": "https://i.chaoxing.com",
            "t": "true",
            "forbidotherlogin": "0",
            "validate": "",
            "doubleFactorLogin": "0",
            "independentId": "0",
        }

        try:
            resp = self.session.post(
                LOGIN_URL, data=login_data, timeout=15, allow_redirects=True
            )
        except Exception as e:
            log.error("登录请求失败: %s", e)
            return False

        # 判断登录结果
        text = resp.text

        def _on_login_ok():
            self._logged_in = True
            self._check_login_cookies()
            if not skip_user_info:
                self._fetch_user_info()

        # HTML 方式返回
        if "恭喜您，登录成功" in text or "登录成功" in text:
            _on_login_ok()
            return True

        # 可能的 JSON 返回
        try:
            data = resp.json()
            if data.get("status") is True or data.get("result") is True:
                _on_login_ok()
                return True
        except (json.JSONDecodeError, ValueError):
            pass

        # Cookie 检查
        if self._check_login_cookies():
            self._logged_in = True
            if not skip_user_info:
                self._fetch_user_info()
            return True

        return False

    def _check_login_cookies(self) -> bool:
        for cookie in self.session.cookies:
            if cookie.name in ("UID", "_uid") and cookie.value:
                self._uid = cookie.value
                return True
        return False

    def _fetch_user_info(self):
        # 先尝试从 cookie 中获取 uid
        self._check_login_cookies()
        # 再尝试从 SSO API 获取更完整的用户信息
        try:
            resp = self.session.get(USER_INFO_URL, timeout=10)
            data = resp.json()
            if "msg" in data:
                msg = data["msg"]
                self._uid = msg.get("uid", self._uid)
                self._name = msg.get("name", self._name or "")
        except Exception as e:
            log.debug("获取用户信息失败: %s", e)

    @property
    def is_logged_in(self) -> bool:
        return self._logged_in

    @property
    def uid(self) -> str:
        return self._uid

    @property
    def name(self) -> str:
        return self._name

    # ================================================================
    # Session 持久化
    # ================================================================

    def save_session(self, filepath: str = "session.json"):
        """保存 cookies 到文件"""
        cookies = self.session.cookies.get_dict()
        data = {"cookies": cookies, "uid": self._uid, "name": self._name}
        Path(filepath).write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                  encoding="utf-8")

    def load_session(self, filepath: str = "session.json") -> bool:
        """从文件恢复 cookies"""
        p = Path(filepath)
        if not p.exists():
            return False
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            cookies = data.get("cookies", {})
            for key, value in cookies.items():
                self.session.cookies.set(key, value)
            self._uid = data.get("uid", "")
            self._name = data.get("name", "")
            self._logged_in = bool(cookies)
            return self._logged_in
        except Exception:
            return False

    # ================================================================
    # 获取课程列表
    # ================================================================

    def get_courses(self) -> list[Course]:
        try:
            resp = self.session.get(COURSE_LIST_URL, timeout=15)
            data = resp.json()
        except Exception as e:
            log.error("获取课程列表失败: %s", e)
            return []

        courses: list[Course] = []

        for channel in data.get("channelList", []):
            # cataid=100000002 才是课程，100000017 是文件夹
            if channel.get("cataid") != "100000002":
                continue

            content = channel.get("content", {})
            if isinstance(content, str):
                content = safe_json_loads(content)

            # content.id = classId, content.name = className
            class_id = str(content.get("id", ""))
            class_name = content.get("name", "")

            # content.course.data[] 是具体课程信息
            course_block = content.get("course", {})
            course_list = course_block.get("data", [])

            for c in course_list:
                if not isinstance(c, dict):
                    continue
                course = Course(
                    course_id=str(c.get("id", "")),
                    class_id=class_id,
                    name=c.get("name", "") or class_name,
                    teacher=c.get("teacherfactor", ""),
                    cover_url=c.get("imageurl", ""),
                )
                if course.course_id and course.name:
                    courses.append(course)

        return courses

    # ================================================================
    # 获取签到活动列表
    # ================================================================

    def get_sign_tasks(self, course: Course, check_signed: bool = False) -> list[SignTask]:
        try:
            resp = self.session.get(ACTIVE_TASK_URL, params={
                "courseId": course.course_id,
                "classId": course.class_id,
                "fid": "0",
                "showNotStartedActive": "0",
            }, timeout=15)
            data = resp.json()
        except Exception as e:
            log.error("获取活动列表失败: %s", e)
            return []

        tasks: list[SignTask] = []

        for item in data.get("activeList", []):
            try:
                atype = int(item.get("activeType", 0))
            except (ValueError, TypeError):
                atype = 0
            if atype != 2:
                continue

            name = item.get("nameOne", "")
            status = "active" if item.get("status") == 1 else "ended"
            raw_url = item.get("url", "")

            active_id = str(item.get("id", ""))
            if not active_id and "activePrimaryId=" in raw_url:
                m = re.search(r"activePrimaryId=(\d+)", raw_url)
                if m:
                    active_id = m.group(1)

            task = SignTask(
                active_id=active_id,
                name=name,
                course_name=course.name,
                course_id=course.course_id,
                class_id=course.class_id,
                sign_type=SignType.from_chinese(name),
                status=status,
                start_time=str(item.get("startTime", "")),
                end_time=str(item.get("endTime", "")),
                raw_url=raw_url,
            )

            # 仅在需要时检测已签到状态（避免不必要请求）
            if check_signed and task.status == "active" and task.active_id:
                task.signed = self.check_signed(task.active_id, task.course_id, task.class_id)

            tasks.append(task)

        return tasks


    def check_signed(self, active_id: str, course_id: str, class_id: str) -> bool:
        """检测某个签到活动当前用户是否已完成签到"""
        try:
            resp = self.session.get(
                "https://mobilelearn.chaoxing.com/widget/sign/pcStuSignController/preSign",
                params={
                    "activeId": active_id,
                    "classId": class_id,
                    "courseId": course_id,
                    "fid": "0",
                },
                timeout=10,
            )
            text = resp.text
            if "签到成功" in text or "已签到" in text or "您已签到" in text:
                return True
            data = safe_json_loads(text)
            if data:
                return data.get("status") is True or "success" in str(data).lower()
        except Exception:
            pass
        return False

    # ================================================================
    # 签到详情分析
    # ================================================================

    def get_sign_detail(self, task: SignTask) -> SignTask:
        """分析签到参数：解析 preSign HTML 提取 acId、坐标等"""
        html = ""
        if task.raw_url:
            try:
                resp = self.session.get(task.raw_url, timeout=10)
                html = resp.text
            except Exception:
                pass

        if not html:
            return task

        # 从 HTML 中提取 acId
        m = re.search(r'acId\s*=\s*["\'](\d+)["\']', html)
        if m:
            task.active_id = m.group(1)

        # 从 URL 中提取 activePrimaryId（备用）
        if not task.active_id and "activePrimaryId=" in task.raw_url:
            m = re.search(r"activePrimaryId=(\d+)", task.raw_url)
            if m:
                task.active_id = m.group(1)

        # 二维码签到：从后续的 API 调用中提取 enc
        if task.sign_type == SignType.QRCODE:
            # 尝试构造详情 URL 获取 enc
            m = re.search(r'url1\s*=\s*["\']([^"\']+)["\']', html)
            if m:
                detail_url = m.group(1)
                try:
                    resp = self.session.get(detail_url, timeout=10)
                    data = safe_json_loads(resp.text)
                    task.enc = data.get("enc", "") or data.get("encStr", "")
                except Exception:
                    pass

        return task

    # ================================================================
    # 执行签到
    # ================================================================

    def sign(self, task: SignTask, **kwargs) -> bool:
        sign_methods = {
            SignType.NORMAL: self._sign_normal,
            SignType.PHOTO: self._sign_photo,
            SignType.GESTURE: self._sign_gesture,
            SignType.LOCATION: self._sign_location,
            SignType.QRCODE: self._sign_qrcode,
            SignType.CODE: self._sign_code,
        }
        method = sign_methods.get(task.sign_type, self._sign_normal)
        return method(task, **kwargs)

    # --------- common params ----------

    def _base_params(self, task: SignTask) -> dict:
        return {
            "activeId": task.active_id,
            "courseId": task.course_id,
            "uid": self._uid,
            "clientip": "",
            "useragent": "",
            "latitude": "-1",
            "longitude": "-1",
            "appType": "15",
            "fid": "0",
        }

    # --------- sign-in methods ----------
    # 原项目逻辑:
    #   普通/拍照/手势/签到码 → 直接调用签到 API
    #   位置签到              → 携带自定义经纬度
    #   二维码签到            → 携带 enc 参数

    def _sign_normal(self, task: SignTask, **kwargs) -> bool:
        """普通签到 — 直接提交，无需额外操作"""
        return self._do_sign_get(task, self._base_params(task))

    def _sign_photo(self, task: SignTask, **kwargs) -> bool:
        """拍照签到 — 不上传图片，按普通签到处理（教师端显示无图）"""
        return self._sign_normal(task, **kwargs)

    def _sign_gesture(self, task: SignTask, **kwargs) -> bool:
        """手势签到 — 其中 gesture 为 [1-9] 连线顺序，如 1235789"""
        gesture = kwargs.get("gesture", "")
        params = self._base_params(task)
        if gesture:
            params["signCode"] = gesture
        return self._do_sign_get(task, params)

    def _sign_code(self, task: SignTask, **kwargs) -> bool:
        """签到码签到 — 优先使用 PC 端点 signIn"""
        code = kwargs.get("code", "")
        params = self._base_params(task)
        if code:
            params["signCode"] = code
        return self._do_sign_get(task, params)

    def _sign_location(self, task: SignTask, **kwargs) -> bool:
        """位置签到 — 携带自定义经纬度（默认北京）"""
        lng = kwargs.get("longitude", task.location_longitude or "116.404")
        lat = kwargs.get("latitude", task.location_latitude or "39.915")

        params = self._base_params(task)
        params["latitude"] = lat
        params["longitude"] = lng
        return self._do_sign_get(task, params)

    def _sign_qrcode(self, task: SignTask, **kwargs) -> bool:
        """二维码签到 — 需 enc 参数，支持: ①直接扫码 ②文件 ③输入内容 ④enc"""
        enc = kwargs.get("enc", task.enc or "")
        if not enc:
            qr_content = kwargs.get("qr_content", "")
            if qr_content:
                m = re.search(r"enc=([a-zA-Z0-9_\-]+)", qr_content)
                enc = m.group(1) if m else qr_content.strip()
        if not enc:
            log.error("二维码签到缺少 enc 参数")
            return False

        params = self._base_params(task)
        params["enc"] = enc
        return self._do_sign_get(task, params)

    def sign_with_uid(self, task: SignTask, target_uid: str, **kwargs) -> bool:
        """为指定 uid 执行签到（代签核心方法）"""
        params = self._base_params(task)
        params["uid"] = target_uid
        if kwargs.get("enc"):
            params["enc"] = kwargs["enc"]
        if kwargs.get("longitude"):
            params["longitude"] = kwargs["longitude"]
            params["latitude"] = kwargs.get("latitude", "-1")
        return self._do_sign_get(task, params)

    def _do_sign_get(self, task: SignTask, params: dict) -> bool:
        """GET 方式调用签到接口"""
        try:
            resp = self.session.get(STUSIGN_URL, params=params, timeout=15)
            text = resp.text.strip()
        except Exception as e:
            log.error("签到请求失败: %s", e)
            return False

        if text == "success":
            return True
        if "成功" in text or "重复" in text or "已签到" in text:
            return True

        # 可能返回 JSON
        result = safe_json_loads(text)
        if isinstance(result, dict):
            if result.get("status") is True or result.get("success") is True:
                return True
            msg = str(result.get("msg", result.get("message", "")))
            if msg and ("成功" in msg or "重复" in msg):
                return True

        log.warning("签到失败, 响应: %s", text[:200])
        return False

    # ================================================================
    # 账户信息
    # ================================================================

    def get_account_info(self) -> AccountInfo:
        info = AccountInfo(uid=self._uid, name=self._name)
        try:
            resp = self.session.get("https://i.chaoxing.com/base", timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")
            el = soup.select_one(".user-con h1")
            if el:
                info.name = el.get_text(strip=True)
            el = soup.select_one(".unit-name h1")
            if el:
                info.school = el.get_text(strip=True)
            el = soup.select_one(".user-con img")
            if el:
                info.avatar = el.get("src", "")
        except Exception:
            pass
        return info
