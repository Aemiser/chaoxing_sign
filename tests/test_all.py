"""单元测试 - 使用 mocker 验证核心逻辑"""
from __future__ import annotations
import json
import pytest
import requests

from chaoxing_sign import ChaoxingClient, Course, SignTask, SignType, AccountInfo
from chaoxing_sign.utils import (
    parse_course_id_from_url,
    extract_enc_from_qr,
    safe_json_loads,
)

from tests.conftest import (
    FakeResponse,
    mock_session_methods,
    make_client,
    LOGIN_PAGE_URL,
)


# ============================================================
# 工具函数测试 (无需 HTTP)
# ============================================================

class TestUtils:
    def test_parse_course_id_from_url(self):
        cid, clid = parse_course_id_from_url("http://x.com?courseid=12345&clazzid=67890")
        assert cid == "12345"
        assert clid == "67890"

    def test_parse_no_match(self):
        cid, clid = parse_course_id_from_url("http://x.com/no-match")
        assert cid == "" and clid == ""

    def test_extract_enc(self):
        assert extract_enc_from_qr("https://x.com?enc=abc123") == "abc123"

    def test_extract_enc_plain(self):
        assert extract_enc_from_qr("ABC") == "ABC"

    def test_safe_json(self):
        assert safe_json_loads('{"a":1}') == {"a": 1}

    def test_safe_json_bad(self):
        assert safe_json_loads("bad") == {}


class TestSignType:
    def test_all_types(self):
        assert SignType.from_chinese("普通签到") == SignType.NORMAL
        assert SignType.from_chinese("拍照签到") == SignType.PHOTO
        assert SignType.from_chinese("手势签到") == SignType.GESTURE
        assert SignType.from_chinese("位置签到") == SignType.LOCATION
        assert SignType.from_chinese("二维码签到") == SignType.QRCODE
        assert SignType.from_chinese("签到码签到") == SignType.CODE

    def test_fallback(self):
        assert SignType.from_chinese("未知") == SignType.NORMAL


class TestDataclasses:
    def test_course_defaults(self):
        c = Course()
        assert c.course_id == ""

    def test_sign_task_defaults(self):
        t = SignTask(active_id="1", name="s", course_name="c", course_id="2", class_id="3")
        assert t.sign_type == SignType.NORMAL
        assert t.enc == ""

    def test_account_info(self):
        assert AccountInfo().uid == ""


# ============================================================
# Client 测试
# ============================================================

class TestClientInit:
    def test_initial(self):
        c = ChaoxingClient()
        assert not c.is_logged_in
        assert c.uid == ""


class TestClientLogin:
    def test_html_success(self, mocker):
        c = make_client(mocker, post_logon={
            "text": "恭喜您，登录成功<script>...</script>",
        })
        assert c.login("13800000000", "pwd") is True
        assert c.is_logged_in

    def test_json_success(self, mocker):
        c = make_client(mocker, post_logon={
            "text": "",
            "json": {"status": True},
        })
        assert c.login("13800000000", "pwd") is True

    def test_cookie_success(self, mocker):
        c = make_client(mocker, post_logon={
            "text": "",
            "cookies": {"UID": "30001"},
        })
        assert c.login("13800000000", "pwd") is True
        assert c.uid == "30001"

    def test_failure(self, mocker):
        c = make_client(mocker, post_logon={
            "text": "用户名或密码错误",
        })
        assert c.login("13800000000", "wrong") is False
        assert not c.is_logged_in


class TestClientCourses:
    def test_get_courses(self, mocker):
        c = make_client(mocker, course_resp={
            "channelList": [
                {
                    "cataid": "100000017",  # 文件夹, 跳过
                    "content": {"folderName": "我的文件夹"},
                },
                {
                    "cataid": "100000002",  # 课程
                    "content": {
                        "id": 456,
                        "name": "计算机类2301",
                        "course": {
                            "data": [{
                                "id": 123,
                                "name": "测试课",
                                "teacherfactor": "张老师",
                            }]
                        },
                    },
                },
            ]
        })
        c._logged_in = True
        courses = c.get_courses()
        assert len(courses) == 1
        assert courses[0].name == "测试课"
        assert courses[0].course_id == "123"
        assert courses[0].class_id == "456"
        assert courses[0].teacher == "张老师"

    def test_empty(self, mocker):
        c = make_client(mocker)
        c._logged_in = True
        assert c.get_courses() == []

    def test_network_error(self, mocker):
        c = ChaoxingClient()
        mocker.patch.object(c.session, "get", side_effect=requests.exceptions.Timeout)
        c._logged_in = True
        assert c.get_courses() == []


class TestClientSignTasks:
    def test_get_tasks(self, mocker):
        c = make_client(mocker, task_resp={
            "activeList": [
                {"id": 1, "nameOne": "手势签到", "activeType": 2, "status": 1},
                {"id": 2, "nameOne": "位置签到", "activeType": 2, "status": 2},
                {"id": 3, "nameOne": "讨论", "activeType": 1, "status": 1},
            ]
        })
        c._logged_in = True
        course = Course(course_id="1", class_id="2", name="课")
        tasks = c.get_sign_tasks(course)
        assert len(tasks) == 2  # 讨论被过滤
        assert tasks[0].sign_type == SignType.GESTURE
        assert tasks[0].status == "active"
        assert tasks[1].status == "ended"

    def test_network_error(self, mocker):
        c = make_client(mocker)
        mocker.patch.object(c.session, "get",
                            side_effect=[FakeResponse("", 200),
                                         requests.exceptions.Timeout])
        c._logged_in = True
        course = Course(course_id="1", class_id="2", name="课")
        assert c.get_sign_tasks(course) == []


class TestSignDetail:
    def _course(self):
        return Course(course_id="1", class_id="2", name="课")

    def test_extract_acId_from_html(self, mocker):
        """从 preSign HTML 中提取 acId"""
        # 构造 HTML 包含 acId = "999888"
        html = '<script>var acId = "999888";</script>'
        resp_data = {"text": html, "code": 200}
        c = make_client(mocker, get_resp=resp_data)
        c._logged_in = True

        t = SignTask("old_id", "普通签到", "课", "1", "2",
                      sign_type=SignType.NORMAL, raw_url="https://x.com/preSign")
        result = c.get_sign_detail(t)
        assert result.active_id == "999888"

    def test_no_raw_url(self, mocker):
        """没有 raw_url 时不做任何修改"""
        c = make_client(mocker)
        c._logged_in = True
        t = SignTask("123", "普通签到", "课", "1", "2", sign_type=SignType.NORMAL)
        result = c.get_sign_detail(t)
        assert result.active_id == "123"  # 不变

    def test_qrcode_extract_enc(self, mocker):
        """二维码签到从 url1 获取 enc"""
        html = '<script>var acId = "999";var url1="https://x.com/detail?activeId=999";</script>'
        # 构造: preSign 返回 HTML，detail URL 返回 enc
        call_count = [0]

        def side_get(url, **kwargs):
            call_count[0] += 1
            if "preSign" in url:
                return FakeResponse(html, 200)
            if "detail" in url:
                return FakeResponse(json_data={"enc": "abc123"})
            return FakeResponse("", 200)

        c = ChaoxingClient()
        c._logged_in = True
        mocker.patch.object(c.session, "get", side_effect=side_get)

        t = SignTask("", "二维码签到", "课", "1", "2",
                      sign_type=SignType.QRCODE, raw_url="https://x.com/preSign")
        result = c.get_sign_detail(t)
        assert result.active_id == "999"
        assert result.enc == "abc123"


class TestSignExecution:
    def _course(self):
        return Course(course_id="1", class_id="2", name="课")

    def _setup(self, mocker, checkin_resp):
        c = make_client(mocker, checkin_resp=checkin_resp, analysis_resp={})
        c._logged_in = True
        c._uid = "10001"
        c._name = "测试"
        return c

    def test_normal(self, mocker):
        c = self._setup(mocker, {"text": "success"})
        t = SignTask("1", "普通签到", "课", "1", "2", sign_type=SignType.NORMAL)
        assert c.sign(t)[0] is True

    def test_gesture(self, mocker):
        c = self._setup(mocker, {"text": "success"})
        t = SignTask("1", "手势签到", "课", "1", "2", sign_type=SignType.GESTURE)
        assert c.sign(t)[0] is True

    def test_location(self, mocker):
        c = self._setup(mocker, {"text": "success"})
        t = SignTask("1", "位置签到", "课", "1", "2", sign_type=SignType.LOCATION)
        assert c.sign(t, longitude="120.5", latitude="30.5")[0] is True

    def test_location_default(self, mocker):
        c = self._setup(mocker, {"text": "success"})
        t = SignTask("1", "位置签到", "课", "1", "2", sign_type=SignType.LOCATION)
        assert c.sign(t)[0] is True  # 默认北京坐标

    def test_qrcode(self, mocker):
        c = self._setup(mocker, {"text": "success"})
        t = SignTask("1", "二维码签到", "课", "1", "2", sign_type=SignType.QRCODE)
        assert c.sign(t, enc="myenc")[0] is True

    def test_qrcode_from_content(self, mocker):
        c = self._setup(mocker, {"text": "success"})
        t = SignTask("1", "二维码签到", "课", "1", "2", sign_type=SignType.QRCODE)
        assert c.sign(t, qr_content="https://x.com?enc=extracted")[0] is True

    def test_qrcode_no_enc(self, mocker):
        c = self._setup(mocker, {"text": "success"})
        t = SignTask("1", "二维码签到", "课", "1", "2", sign_type=SignType.QRCODE)
        assert c.sign(t)[0] is False

    def test_code(self, mocker):
        c = self._setup(mocker, {"text": "success"})
        t = SignTask("1", "签到码签到", "课", "1", "2", sign_type=SignType.CODE)
        assert c.sign(t)[0] is True

    def test_json_response(self, mocker):
        c = self._setup(mocker, {"json": {"status": True}})
        t = SignTask("1", "普通签到", "课", "1", "2", sign_type=SignType.NORMAL)
        assert c.sign(t)[0] is True

    def test_network_error(self, mocker):
        c = ChaoxingClient()
        mocker.patch.object(c.session, "get", return_value=FakeResponse("{}"))
        mocker.patch.object(c.session, "post",
                            side_effect=requests.exceptions.Timeout)
        c._logged_in = True
        t = SignTask("1", "普通签到", "课", "1", "2", sign_type=SignType.NORMAL)
        assert c.sign(t)[0] is False

    def test_photo(self, mocker):
        """拍照签到 = 普通签到"""
        c = self._setup(mocker, {"text": "success"})
        t = SignTask("1", "拍照签到", "课", "1", "2", sign_type=SignType.PHOTO)
        assert c.sign(t)[0] is True


class TestSessionPersistence:
    def test_save_and_load(self, tmp_path):
        c = ChaoxingClient()
        c._uid = "123"
        c._name = "test"
        c._logged_in = True
        c.session.cookies.set("key", "val")

        fp = str(tmp_path / "s.json")
        c.save_session(fp)

        c2 = ChaoxingClient()
        assert c2.load_session(fp) is True
        assert c2._uid == "123"
        assert c2._name == "test"
        assert c2.is_logged_in is True

    def test_missing_file(self):
        assert ChaoxingClient().load_session("no.json") is False