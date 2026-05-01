"""请求/响应 Pydantic 模型"""
from __future__ import annotations
from pydantic import BaseModel


class AddFriendRequest(BaseModel):
    target_account: str


class QrcodeSignRequest(BaseModel):
    qr_data: str
    active_id: str = ""
    course_id: str = ""
    class_id: str = ""
    proxy_friend_ids: list[int] = []
    sign_type: str = ""
    longitude: str = ""
    latitude: str = ""
    location_name: str = ""
    use_trilateration: str = "1"
