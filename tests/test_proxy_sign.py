"""代签功能单元测试"""
import pytest
from unittest.mock import MagicMock, patch

from chaoxing_sign.types import SignTask, SignType
from chaoxing_sign.client import ChaoxingClient


class TestSignWithUid:
    def test_sign_with_uid_overrides_params(self):
        """代理签到使用目标用户的 uid"""
        client = ChaoxingClient()
        client._uid = "self_uid"

        task = SignTask(
            active_id="111",
            course_id="222",
            class_id="333",
            sign_type=SignType.QRCODE,
        )

        # Mock _do_sign_get 来捕获参数
        called_params = {}

        def capture_params(t, params):
            called_params.update(params)
            return True

        client._do_sign_get = capture_params

        result = client.sign_with_uid(task, "target_uid_999", enc="enc_abc")
        assert result is True
        assert called_params["uid"] == "target_uid_999"
        assert called_params["enc"] == "enc_abc"
        assert called_params["activeId"] == "111"
        assert called_params["courseId"] == "222"

    def test_sign_with_uid_no_enc(self):
        """不带 enc 的代签"""
        client = ChaoxingClient()
        client._uid = "self_uid"

        task = SignTask(
            active_id="111",
            course_id="222",
            class_id="333",
            sign_type=SignType.NORMAL,
        )

        called_params = {}

        def capture_params(t, params):
            called_params.update(params)
            return False

        client._do_sign_get = capture_params
        result = client.sign_with_uid(task, "other_uid")
        assert result is False
        assert called_params["uid"] == "other_uid"
        assert "enc" not in called_params

    def test_sign_with_uid_with_location(self):
        """位置代签"""
        client = ChaoxingClient()
        client._uid = "self_uid"

        task = SignTask(
            active_id="111",
            course_id="222",
            class_id="333",
            sign_type=SignType.LOCATION,
        )

        called_params = {}

        def capture_params(t, params):
            called_params.update(params)
            return True

        client._do_sign_get = capture_params
        result = client.sign_with_uid(
            task, "target_uid",
            longitude="120.123", latitude="30.456",
        )
        assert result is True
        assert called_params["uid"] == "target_uid"
        assert called_params["longitude"] == "120.123"
        assert called_params["latitude"] == "30.456"


class TestProxyQrcodeFlow:
    def test_enc_extraction_from_qr_data(self):
        """从二维码数据中提取 enc"""
        import re
        qr_data = "https://example.com/sign?courseId=123&enc=abc_xyz_999"
        m = re.search(r"enc=([a-zA-Z0-9_\-]+)", qr_data)
        assert m
        assert m.group(1) == "abc_xyz_999"

    def test_enc_extraction_no_match(self):
        """无 enc 时的回退"""
        qr_data = "some_plain_enc_value"
        import re
        m = re.search(r"enc=([a-zA-Z0-9_\-]+)", qr_data)
        if not m:
            enc = qr_data.strip()
        assert enc == qr_data

    def test_base_params_include_uid(self):
        """基础参数包含登录用户 uid"""
        client = ChaoxingClient()
        client._uid = "my_uid"
        task = SignTask(
            active_id="a1",
            course_id="c1",
            class_id="cl1",
            sign_type=SignType.NORMAL,
        )
        params = client._base_params(task)
        assert params["uid"] == "my_uid"
        assert params["activeId"] == "a1"
        assert params["courseId"] == "c1"
        assert params["latitude"] == "-1"
        assert params["longitude"] == "-1"
        assert params["appType"] == "15"
