"""ORM 模型：用户、好友关系、代签记录"""
from sqlalchemy import (
    Column, Integer, BigInteger, String, DateTime, Text,
    ForeignKey, UniqueConstraint, func,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    supernova_account = Column(String(64), unique=True, nullable=False, index=True)
    username = Column(String(64), default="")
    nickname = Column(String(128), default="")
    avatar = Column(String(512), default="")
    school = Column(String(255), default="")
    location = Column(String(255), default="")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Friendship(Base):
    __tablename__ = "friendships"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    friend_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "friend_id"),)


class CourseRecord(Base):
    """用户课程缓存表 — 首次登录时从超星 API 拉取并存储，后续可同步更新"""
    __tablename__ = "course_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    course_id = Column(String(64), nullable=False)
    class_id = Column(String(64), nullable=False)
    name = Column(String(256), default="")
    teacher = Column(String(128), default="")
    cover_url = Column(String(512), default="")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "course_id", "class_id", name="uq_user_course"),
    )


class ProxyRecord(Base):
    __tablename__ = "proxy_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    target_uid = Column(String(64), nullable=False)
    active_id = Column(String(64), nullable=False)
    enc = Column(String(255), default="")
    result = Column(String(32), default="")
    actionuser = Column(String(64), default="")
    friendids = Column(String(512), default="")
    created_at = Column(DateTime, server_default=func.now())


class TaskSignCache(Base):
    __tablename__ = "task_sign_cache"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    active_id = Column(String(64), nullable=False)
    course_id = Column(String(64), nullable=False)
    class_id = Column(String(64), nullable=False)
    task_data = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())


class UserSession(Base):
    """持久化超星会话（cookies），供代签时使用好友的会话执行签到"""
    __tablename__ = "user_sessions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    cookies_json = Column(Text, nullable=False)
    uid = Column(String(64), default="")
    name = Column(String(128), default="")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
