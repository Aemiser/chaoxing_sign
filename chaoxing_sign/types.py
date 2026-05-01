"""数据类型定义"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SignType(Enum):
    """签到类型

    每个成员包含 (API 标识名, 中文显示名)，可直接通过 .label 获取。
    """

    NORMAL = ("normal", "普通签到")
    PHOTO = ("photo", "拍照签到")
    GESTURE = ("gesture", "手势签到")
    LOCATION = ("location", "位置签到")
    QRCODE = ("qrcode", "二维码签到")
    QRCODE_LOCATION = ("qrcode_location", "指定位置二维码签到")
    CODE = ("code", "签到码签到")

    def __new__(cls, api_value: str, label: str = ""):
        obj = object.__new__(cls)
        obj._value_ = api_value      # .value 仍返回 "qrcode" 等 API 字符串
        obj._label = label            # .label 返回 "二维码签到" 等中文显示名
        return obj

    @property
    def label(self) -> str:
        """中文显示名，如 "二维码签到" """
        return self._label

    @classmethod
    def from_chinese(cls, name: str) -> "SignType":
        """从 API 返回的任务名推断签到类型（如 "手势签到" → SignType.GESTURE）"""
        for keyword, member in _SIGN_TYPE_KEYWORDS.items():
            if keyword in name:
                return member
        return cls.NORMAL


# 中文关键词 → 签到类型（from_chinese 使用，模块级避免被 enum 当做成员）
_SIGN_TYPE_KEYWORDS: dict[str, SignType] = {
    "普通": SignType.NORMAL,
    "拍照": SignType.PHOTO,
    "手势": SignType.GESTURE,
    "位置": SignType.LOCATION,
    "二维码": SignType.QRCODE,
    "签到码": SignType.CODE,
}

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
    signed: bool = False     # 当前用户是否已签到
    start_time: str = ""
    end_time: str = ""
    raw_url: str = ""

    # 签到需要的额外参数
    enc: str = ""             # 二维码签到的 enc 参数
    location_latitude: str = ""
    location_longitude: str = ""
    location_name: str = ""
