"""数据类型定义"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SignType(Enum):
    """签到类型"""
    NORMAL = "normal"        # 普通签到
    PHOTO = "photo"          # 拍照签到
    GESTURE = "gesture"      # 手势签到
    LOCATION = "location"    # 位置签到
    QRCODE = "qrcode"        # 二维码签到
    CODE = "code"            # 签到码签到

    @classmethod
    def from_chinese(cls, name: str) -> "SignType":
        mapping = {
            "普通": cls.NORMAL,
            "拍照": cls.PHOTO,
            "手势": cls.GESTURE,
            "位置": cls.LOCATION,
            "二维码": cls.QRCODE,
            "签到码": cls.CODE,
        }
        for key, val in mapping.items():
            if key in name:
                return val
        return cls.NORMAL


@dataclass
class AccountInfo:
    """账户信息"""
    uid: str = ""
    name: str = ""
    school: str = ""
    avatar: str = ""


@dataclass
class Course:
    """课程信息"""
    course_id: str = ""
    class_id: str = ""
    name: str = ""
    teacher: str = ""
    cover_url: str = ""


@dataclass
class SignTask:
    """签到任务"""
    active_id: str = ""
    name: str = ""
    course_name: str = ""
    course_id: str = ""
    class_id: str = ""
    sign_type: SignType = SignType.NORMAL
    status: str = ""         # "active" / "ended"
    start_time: str = ""
    end_time: str = ""
    raw_url: str = ""

    # 签到需要的额外参数
    enc: str = ""             # 二维码签到的 enc 参数
    location_latitude: str = ""
    location_longitude: str = ""
    location_name: str = ""
