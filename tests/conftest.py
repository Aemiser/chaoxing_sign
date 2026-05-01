"""共享 pytest fixtures — FakeResponse, mock helpers, client factory"""
from __future__ import annotations
import json
import pytest

from chaoxing_sign import ChaoxingClient
from chaoxing_sign.core.constants import (
    STUSIGN_URL, PRESIGN_URL, ACTIVE_TASK_URL, COURSE_LIST_URL,
    LOGIN_URL, USER_INFO_URL, PASSPORT_HOST,
)

LOGIN_PAGE_URL = f"{PASSPORT_HOST}/login?newversion=true"


class FakeResponse:
    """模拟 requests.Response"""

    def __init__(self, text="", status_code=200, json_data=None, cookies=None):
        if json_data is not None and not text:
            text = json.dumps(json_data, ensure_ascii=False)
        self._text = text
        self.status_code = status_code
        self._json_data = json_data
        self._cookies = cookies or {}

    @property
    def text(self):
        return self._text

    def json(self):
        if self._json_data is not None:
            return self._json_data
        return json.loads(self._text)


def mock_session_methods(mocker, client, get_pages=True, get_resp=None,
                          post_logon=None, course_resp=None,
                          task_resp=None, analysis_resp=None,
                          checkin_resp=None):
    """统一 mock Session 的 get/post 方法"""
    session = client.session

    def _fake_get(url, **kwargs):
        if get_pages and LOGIN_PAGE_URL in url:
            return FakeResponse("", 200)
        if USER_INFO_URL in url:
            return FakeResponse(json_data={"msg": {"uid": client._uid or "10001", "name": "test"}})
        if COURSE_LIST_URL in url:
            if course_resp:
                return FakeResponse(json_data=course_resp)
            return FakeResponse(json_data={"channelList": []})
        if ACTIVE_TASK_URL in url:
            if task_resp:
                return FakeResponse(json_data=task_resp)
            return FakeResponse(json_data={"activeList": []})
        if PRESIGN_URL in url:
            if analysis_resp:
                return FakeResponse(json_data=analysis_resp)
            return FakeResponse(json_data={})
        if STUSIGN_URL in url and checkin_resp:
            return FakeResponse(
                text=checkin_resp.get("text", ""),
                status_code=checkin_resp.get("code", 200),
                json_data=checkin_resp.get("json"),
            )
        if get_resp:
            return FakeResponse(text=get_resp.get("text", ""), status_code=get_resp.get("code", 200))
        return FakeResponse("", 200)

    def _fake_post(url, data=None, **kwargs):
        if LOGIN_URL in url:
            if post_logon:
                for k, v in post_logon.get("cookies", {}).items():
                    client.session.cookies.set(k, v)
                return FakeResponse(
                    text=post_logon.get("text", ""),
                    status_code=post_logon.get("code", 200),
                    json_data=post_logon.get("json"),
                )
            return FakeResponse("login failed", 200)
        return FakeResponse("", 200)

    mocker.patch.object(session, "get", side_effect=_fake_get)
    mocker.patch.object(session, "post", side_effect=_fake_post)


def make_client(mocker, **kwargs):
    """创建已 mock 的 ChaoxingClient"""
    client = ChaoxingClient()
    mock_session_methods(mocker, client, **kwargs)
    return client


@pytest.fixture
def fake_client(mocker):
    """pytest fixture: 返回已 mock 的 ChaoxingClient（未登录）"""
    return make_client(mocker)


@pytest.fixture
def logged_in_client(mocker):
    """pytest fixture: 返回已 mock 且已登录的 ChaoxingClient"""
    c = make_client(mocker)
    c._logged_in = True
    c._uid = "10001"
    c._name = "test_user"
    return c
