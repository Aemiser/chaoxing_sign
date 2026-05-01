"""测试签到码签到请求"""

from __future__ import annotations
import pytest
import requests

from chaoxing_sign import ChaoxingClient, Course, SignTask, SignType


class TestCodeSign:
    def _make_client(self, mocker, **kwargs):
        from tests.conftest import make_client

        c = make_client(mocker, **kwargs)
        c._logged_in = True
        c._uid = "10001"
        c._name = "测试用户"
        return c

    def test_code_sign_success(self, mocker):
        """签到码签到成功"""
        c = self._make_client(mocker, checkin_resp={"text": "success"})
        t = SignTask(
            "10086", "签到码签到", "测试课", "123", "456", sign_type=SignType.CODE
        )
        assert c.sign(t)[0] is True

    def test_code_sign_json_success(self, mocker):
        """签到码签到成功 (JSON 响应)"""
        c = self._make_client(mocker, checkin_resp={"json": {"status": True}})
        t = SignTask(
            "10086", "签到码签到", "测试课", "123", "456", sign_type=SignType.CODE
        )
        assert c.sign(t)[0] is True

    def test_code_sign_already_signed(self, mocker):
        """签到码签到 - 已签到 (重复签到视为成功)"""
        c = self._make_client(
            mocker, checkin_resp={"text": "该用户已签到，请不要重复签到"}
        )
        t = SignTask(
            "10086", "签到码签到", "测试课", "123", "456", sign_type=SignType.CODE
        )
        assert c.sign(t)[0] is True

    def test_code_sign_failure(self, mocker):
        """签到码签到失败"""
        c = self._make_client(mocker, checkin_resp={"text": "签到已结束"})
        t = SignTask(
            "10086", "签到码签到", "测试课", "123", "456", sign_type=SignType.CODE
        )
        assert c.sign(t)[0] is False

    def test_code_sign_network_error(self, mocker):
        """签到码签到网络异常"""
        c = ChaoxingClient()
        from tests.conftest import FakeResponse

        mocker.patch.object(c.session, "get", return_value=FakeResponse("{}"))
        mocker.patch.object(c.session, "post", side_effect=requests.exceptions.Timeout)
        c._logged_in = True
        t = SignTask(
            "10086", "签到码签到", "测试课", "123", "456", sign_type=SignType.CODE
        )
        assert c.sign(t)[0] is False

    def test_code_sign_extra_kwargs_ignored(self, mocker):
        """签到码签到忽略额外参数 (正常完成签到)"""
        c = self._make_client(mocker, checkin_resp={"text": "success"})
        t = SignTask(
            "10086", "签到码签到", "测试课", "123", "456", sign_type=SignType.CODE
        )
        assert c.sign(t, sign_code="1234", foo="bar")[0] is True
