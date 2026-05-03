"""核心API客户端 - 登录、课程、活动、签到"""
from __future__ import annotations
import re
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import urllib3
import requests

# solve_captcha 在 _do_sign_get 中延迟导入，避免循环依赖

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from bs4 import BeautifulSoup

from .types import Course, SignTask, SignType, AccountInfo
from .utils import safe_json_loads
from .core.constants import (
    PASSPORT_HOST, MOBILE_API, MOOC_API, SSO_API,
    LOGIN_URL, USER_INFO_URL, COURSE_LIST_URL, ACTIVE_TASK_URL,
    PRESIGN_URL, STUSIGN_URL, SIGN_IN_URL, QRCODE_SIGN_URL, LOCATION_SIGN_URL,
    ANDROID_UA, HEADERS,
)
from .core.sign import SignExecutor
from .logging_config import get_logger

log = get_logger(__name__)


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

        self.session.verify = False

        # 签到执行器（策略模式 — 各类型签到逻辑已拆分到 core/sign.py）
        self._executor = SignExecutor(self)

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

        from .redis_client import cache_sign_task, update_cached_task_location

        tasks: list[SignTask] = []
        to_check_signed: list[SignTask] = []

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

            # 缓存活跃任务到 Redis（TTL = 活动结束时间），已结束的不缓存
            cache_sign_task(item, course.course_id, course.class_id)

            if check_signed and task.status == "active" and task.active_id:
                to_check_signed.append(task)

            tasks.append(task)

        # 并行检测已签到状态
        if to_check_signed:
            cookies = self.session.cookies.get_dict()
            headers = dict(self.session.headers)

            def _check(task):
                s = requests.Session()
                s.headers.update(headers)
                for k, v in cookies.items():
                    s.cookies.set(k, v)
                try:
                    resp = s.get(
                        "https://mobilelearn.chaoxing.com/widget/sign/pcStuSignController/preSign",
                        params={
                            "activeId": task.active_id,
                            "classId": task.class_id,
                            "courseId": task.course_id,
                            "fid": "0",
                        },
                        timeout=10,
                    )
                    task.signed = "您已签到" in resp.text or "签到成功" in resp.text
                except Exception:
                    pass
                finally:
                    s.close()

            with ThreadPoolExecutor(max_workers=5) as pool:
                futures = {pool.submit(_check, t): t for t in to_check_signed}
                for fut in as_completed(futures):
                    try:
                        fut.result()
                    except Exception:
                        pass

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

        # 追踪需要更新到缓存的字段
        cache_updates: dict = {}
        orig_sign_type = task.sign_type.value

        # 检测是否为指定地点签到（二维码 + 位置均检测 #ifopenAddress）
        if task.sign_type in (SignType.QRCODE, SignType.LOCATION):
            soup = BeautifulSoup(html, "lxml")
            el = soup.select_one("#ifopenAddress")
            if el and el.get("value") == "1":
                if task.sign_type == SignType.QRCODE:
                    task.sign_type = SignType.QRCODE_LOCATION
                loc_el = soup.select_one("#locationText")
                if loc_el and loc_el.get("value"):
                    task.location_name = loc_el.get("value")
                    cache_updates["location_name"] = task.location_name
                log.info("检测到指定地点签到: %s", task.location_name)

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
                    if task.enc:
                        cache_updates["enc"] = task.enc
                except Exception:
                    pass

        # 如果 sign_type 变了（如 qrcode→qrcode_location），更新缓存
        if task.sign_type.value != orig_sign_type:
            cache_updates["sign_type"] = task.sign_type.value
            cache_updates["sign_type_label"] = task.sign_type.value

        # 批量写入 Redis 缓存
        if cache_updates:
            from .redis_client import update_cached_task_detail
            update_cached_task_detail(
                task.course_id, task.class_id, task.active_id,
                sign_type=cache_updates.get("sign_type", ""),
                enc=cache_updates.get("enc", ""),
                location_name=cache_updates.get("location_name", ""),
            )

        return task

    def get_sign_details_batch(self, tasks: list[SignTask], max_workers: int = 5) -> None:
        """并行获取多个签到任务的详情（替代串行调用 get_sign_detail）

        每个线程使用独立 requests.Session，共享主 session 的 cookies 和 headers。
        """
        cookies = self.session.cookies.get_dict()
        headers = dict(self.session.headers)

        def _detail(task: SignTask):
            s = requests.Session()
            s.headers.update(headers)
            for k, v in cookies.items():
                s.cookies.set(k, v)
            self._get_sign_detail_with_session(task, s)
            s.close()

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_detail, t): t for t in tasks}
            for fut in as_completed(futures):
                try:
                    fut.result()
                except Exception:
                    pass

    def _get_sign_detail_with_session(self, task: SignTask, s: requests.Session) -> SignTask:
        """get_sign_detail 的独立 session 版本（供并行调用）"""
        from bs4 import BeautifulSoup
        from .utils.json_utils import safe_json_loads

        html = ""
        if task.raw_url:
            try:
                resp = s.get(task.raw_url, timeout=10)
                html = resp.text
            except Exception:
                pass

        if not html:
            return task

        m = re.search(r'acId\s*=\s*["\'](\d+)["\']', html)
        if m:
            task.active_id = m.group(1)

        if not task.active_id and "activePrimaryId=" in task.raw_url:
            m = re.search(r"activePrimaryId=(\d+)", task.raw_url)
            if m:
                task.active_id = m.group(1)

        # 追踪需要更新到缓存的字段
        cache_updates: dict = {}
        orig_sign_type = task.sign_type.value

        if task.sign_type in (SignType.QRCODE, SignType.LOCATION):
            soup = BeautifulSoup(html, "lxml")
            el = soup.select_one("#ifopenAddress")
            if el and el.get("value") == "1":
                if task.sign_type == SignType.QRCODE:
                    task.sign_type = SignType.QRCODE_LOCATION
                loc_el = soup.select_one("#locationText")
                if loc_el and loc_el.get("value"):
                    task.location_name = loc_el.get("value")
                    cache_updates["location_name"] = task.location_name
                log.info("检测到指定地点签到: %s", task.location_name)

        if task.sign_type == SignType.QRCODE:
            m = re.search(r'url1\s*=\s*["\']([^"\']+)["\']', html)
            if m:
                detail_url = m.group(1)
                try:
                    resp = s.get(detail_url, timeout=10)
                    data = safe_json_loads(resp.text)
                    task.enc = data.get("enc", "") or data.get("encStr", "")
                    if task.enc:
                        cache_updates["enc"] = task.enc
                except Exception:
                    pass

        # 如果 sign_type 变了（如 qrcode→qrcode_location），更新缓存
        if task.sign_type.value != orig_sign_type:
            cache_updates["sign_type"] = task.sign_type.value
            cache_updates["sign_type_label"] = task.sign_type.value

        # 批量写入 Redis 缓存
        if cache_updates:
            from .redis_client import update_cached_task_detail
            update_cached_task_detail(
                task.course_id, task.class_id, task.active_id,
                sign_type=cache_updates.get("sign_type", ""),
                enc=cache_updates.get("enc", ""),
                location_name=cache_updates.get("location_name", ""),
            )

        return task

    # ================================================================
    # 执行签到
    # ================================================================

    def sign(self, task: SignTask, **kwargs) -> "tuple[bool, str]":
        """执行签到 — 委托给 SignExecutor（策略模式）

        Returns (ok, message)
        """
        return self._executor.execute(task, **kwargs)

    def sign_with_uid(self, task: SignTask, target_uid: str, **kwargs) -> "tuple[bool, str]":
        """为指定 uid 执行签到（代签核心方法）— 委托给 SignExecutor

        Returns (ok, message)
        """
        return self._executor.execute_with_uid(task, target_uid, **kwargs)

    # ── 底层工具（供 SignExecutor 回调） ──

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

    def _do_sign_get(self, task: SignTask, params: dict) -> "tuple[bool, str]":
        """GET 方式调用签到接口，自动处理滑块验证码

        Returns (ok, message) —  message 包含成功或失败的具体原因。
        """
        from .utils.captcha import solve_captcha
        try:
            validate = solve_captcha(self.session, referer=STUSIGN_URL)
            if validate:
                params["validate"] = validate
        except Exception as e:
            log.debug("滑块验证码处理失败（可能不需要验证码）: %s", e)

        try:
            resp = self.session.get(STUSIGN_URL, params=params, timeout=15)
            text = resp.text.strip()
        except Exception as e:
            log.error("签到请求失败: %s", e)
            return (False, f"网络请求失败: {e}")

        if text == "success":
            return (True, "签到成功")
        if "成功" in text or "重复" in text or "已签到" in text:
            return (True, "签到成功")

        # 可能返回 JSON
        result = safe_json_loads(text)
        if isinstance(result, dict):
            if result.get("status") is True or result.get("success") is True:
                return (True, "签到成功")
            msg = str(result.get("msg", result.get("message", "")))
            if msg and ("成功" in msg or "重复" in msg):
                return (True, "签到成功")

        # 尝试从 JSON 响应中提取具体错误消息
        if isinstance(result, dict):
            msg = str(result.get("msg", result.get("message", "")))
            if msg:
                log.warning(" %s", msg)
                return (False, msg)

        log.warning("签到失败, 响应: %s", text[:200])
        return (False, f" {text[:200]}")

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
