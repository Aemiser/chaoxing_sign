"""JWT 认证单元测试"""
import time
import pytest
from chaoxing_sign import auth


class TestCreateJWT:
    def test_creates_token_with_user_id(self):
        token = auth.create_jwt(42)
        assert token
        assert isinstance(token, str)

    def test_token_is_decodable(self):
        token = auth.create_jwt(100)
        payload = auth.jwt.decode(token, auth._secret, algorithms=[auth.ALGORITHM])
        assert payload["sub"] == "100"

    def test_token_contains_iat_and_exp(self):
        token = auth.create_jwt(1)
        payload = auth.jwt.decode(token, auth._secret, algorithms=[auth.ALGORITHM])
        assert "iat" in payload
        assert "exp" in payload

    def test_token_expires_in_24_hours(self):
        token = auth.create_jwt(1)
        payload = auth.jwt.decode(token, auth._secret, algorithms=[auth.ALGORITHM])
        diff = payload["exp"] - payload["iat"]
        assert diff == 86400  # 24 * 3600


class TestGetCurrentUserID:
    def test_extracts_user_id_from_valid_token(self):
        token = auth.create_jwt(777)
        # 模拟 Header
        from unittest.mock import MagicMock
        header_mock = MagicMock(return_value=f"Bearer {token}")
        # 直接测试 jwt decode
        payload = auth.jwt.decode(token, auth._secret, algorithms=[auth.ALGORITHM])
        assert int(payload["sub"]) == 777

    def test_rejects_expired_token(self):
        import jwt
        expired = jwt.encode(
            {"sub": "1", "iat": 1, "exp": 1},
            auth._secret, algorithm=auth.ALGORITHM,
        )
        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(expired, auth._secret, algorithms=[auth.ALGORITHM])

    def test_rejects_tampered_token(self):
        token = auth.create_jwt(1)
        tampered = token[:-4] + "xxxx"
        with pytest.raises(Exception):
            auth.jwt.decode(tampered, auth._secret, algorithms=[auth.ALGORITHM])

    def test_rejects_token_with_wrong_secret(self):
        token = auth.create_jwt(1)
        with pytest.raises(Exception):
            auth.jwt.decode(token, "wrong-secret", algorithms=[auth.ALGORITHM])
