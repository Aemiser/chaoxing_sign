"""reverse_geocode 单元测试"""
import pytest
import requests
from unittest.mock import MagicMock, patch

from chaoxing_sign.utils import reverse_geocode, reverse_geocode_amap


class TestReverseGeocode:
    def test_returns_structured_address(self):
        """正常返回结构化地址信息"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "display_name": "北京市海淀区中关村",
            "address": {
                "country": "中国",
                "province": "北京市",
                "city": "北京市",
                "district": "海淀区",
                "road": "中关村大街",
            },
            "lat": "39.9042",
            "lon": "116.4074",
        }
        mock_resp.raise_for_status.return_value = None

        with patch("chaoxing_sign.utils.geo.requests.get", return_value=mock_resp) as mock_get:
            result = reverse_geocode(39.9042, 116.4074)

        assert result["display_name"] == "北京市海淀区中关村"
        assert result["address"]["country"] == "中国"
        assert result["address"]["district"] == "海淀区"
        assert result["lat"] == 39.9042
        assert result["lon"] == 116.4074

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args[1]["params"]["lat"] == 39.9042
        assert call_args[1]["params"]["lon"] == 116.4074
        assert call_args[1]["params"]["format"] == "json"
        assert call_args[1]["params"]["accept-language"] == "zh"

    def test_chinese_language_by_default(self):
        """默认请求中文结果"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "display_name": "海淀区, 北京市, 中国",
            "address": {"country": "中国", "city": "北京市"},
            "lat": "39.90",
            "lon": "116.40",
        }
        mock_resp.raise_for_status.return_value = None

        with patch("chaoxing_sign.utils.geo.requests.get", return_value=mock_resp) as mock_get:
            reverse_geocode(39.9, 116.4)

        assert mock_get.call_args[1]["params"]["accept-language"] == "zh"

    def test_custom_language(self):
        """支持自定义语言"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "display_name": "Haidian, Beijing, China",
            "address": {},
            "lat": "39.90",
            "lon": "116.40",
        }
        mock_resp.raise_for_status.return_value = None

        with patch("chaoxing_sign.utils.geo.requests.get", return_value=mock_resp):
            result = reverse_geocode(39.9, 116.4, lang="en")

        assert "Haidian" in result["display_name"]

    def test_network_error(self):
        """网络错误时返回 error 字段"""
        with patch("chaoxing_sign.utils.geo.requests.get",
                   side_effect=requests.ConnectionError("Connection refused")):
            result = reverse_geocode(39.9, 116.4)

        assert "error" in result
        assert "Connection refused" in result["error"]
        assert result["lat"] == 39.9
        assert result["lon"] == 116.4

    def test_api_error_in_response(self):
        """API 返回 error 字段时透传"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"error": "Unable to geocode"}
        mock_resp.raise_for_status.return_value = None

        with patch("chaoxing_sign.utils.geo.requests.get", return_value=mock_resp):
            result = reverse_geocode(0, 0)

        assert result["error"] == "Unable to geocode"

    def test_timeout_propagates(self):
        """超时参数正确传递"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"display_name": "x", "address": {}, "lat": "0", "lon": "0"}
        mock_resp.raise_for_status.return_value = None

        with patch("chaoxing_sign.utils.geo.requests.get", return_value=mock_resp) as mock_get:
            reverse_geocode(39.9, 116.4, timeout=5)

        assert mock_get.call_args[1]["timeout"] == 5

    def test_reverse_geocode(self):
        result = reverse_geocode(23.305371, 113.56789)
        print(result)


class TestReverseGeocodeAmap:
    def test_returns_structured_address(self):
        """正常返回结构化地址信息"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "status": "1",
            "regeocode": {
                "formatted_address": "北京市海淀区中关村大街27号",
                "addressComponent": {
                    "country": "中国",
                    "province": "北京市",
                    "city": "北京市",
                    "district": "海淀区",
                    "township": "中关村街道",
                    "streetNumber": {"street": "中关村大街", "number": "27号"},
                    "adcode": "110108",
                },
            },
        }
        mock_resp.raise_for_status.return_value = None

        with patch("chaoxing_sign.utils.geo.requests.get", return_value=mock_resp) as mock_get:
            result = reverse_geocode_amap(39.9042, 116.4074)

        assert result["display_name"] == "北京市海淀区中关村大街27号"
        assert result["address"]["province"] == "北京市"
        assert result["address"]["district"] == "海淀区"
        assert result["address"]["street"] == "中关村大街"
        assert result["adcode"] == "110108"
        assert result["lat"] == 39.9042
        assert result["lon"] == 116.4074

        call_args = mock_get.call_args
        assert call_args[1]["params"]["location"] == "116.4074,39.9042"

    def test_sends_lon_lat_order(self):
        """高德 API 要求 lon,lat 顺序"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "status": "1",
            "regeocode": {"formatted_address": "x", "addressComponent": {}},
        }
        mock_resp.raise_for_status.return_value = None

        with patch("chaoxing_sign.utils.geo.requests.get", return_value=mock_resp) as mock_get:
            reverse_geocode_amap(23.0, 113.0)

        assert mock_get.call_args[1]["params"]["location"] == "113.0,23.0"

    def test_api_error_status(self):
        """status != 1 时返回 error"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "status": "0",
            "info": "INVALID_USER_KEY",
        }
        mock_resp.raise_for_status.return_value = None

        with patch("chaoxing_sign.utils.geo.requests.get", return_value=mock_resp):
            result = reverse_geocode_amap(39.9, 116.4)

        assert "error" in result
        assert "INVALID_USER_KEY" in result["error"]

    def test_network_error(self):
        """网络错误时返回 error 字段"""
        with patch("chaoxing_sign.utils.geo.requests.get",
                   side_effect=requests.ConnectionError("timeout")):
            result = reverse_geocode_amap(39.9, 116.4)

        assert "error" in result
        assert "timeout" in result["error"]
        assert result["lat"] == 39.9

    def test_amap_live(self):
        """正常返回示例"""
        result = reverse_geocode_amap(23.305371, 113.56789)
        print(result)
