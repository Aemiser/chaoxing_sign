#!/usr/bin/env python3
"""超星学习通签到 - FastAPI Web 服务（好友系统 + 代签功能）"""
from __future__ import annotations
import uuid
import json
import re
import logging
from pathlib import Path

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from chaoxing_sign import ChaoxingClient, SignType
from chaoxing_sign.types import Course, SignTask
from chaoxing_sign import database as db_module
from chaoxing_sign.models import Base, User, Friendship, ProxyRecord, UserSession
from chaoxing_sign.auth import create_jwt, get_current_user_id

log = logging.getLogger("server")
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(application: FastAPI):
    # 启动
    global db_available
    try:
        db_module.init_db(cfg)
        Base.metadata.create_all(bind=db_module.engine)
        test_db = db_module.SessionLocal()
        test_db.close()
        db_available = True
        log.info("数据库连接成功，好友/代签功能已启用")
    except Exception as e:
        db_available = False
        log.warning("数据库不可用，好友/代签功能已禁用: %s", e)
    yield


app = FastAPI(title="超星学习通签到", version="3.0", lifespan=lifespan)

# 静态文件
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Session 池: token → ChaoxingClient
sessions: dict[str, ChaoxingClient] = {}

# DB 是否可用
db_available = False

# 加载配置
config_path = Path(__file__).parent / "config.json"
default_location = {"longitude": "116.404", "latitude": "39.915", "name": "北京市"}
cfg: dict = {}
if config_path.exists():
    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
        default_location.update(cfg.get("location", {}))
    except Exception:
        pass


# ================================================================
# 请求体模型
# ================================================================

class AddFriendRequest(BaseModel):
    target_account: str


class QrcodeSignRequest(BaseModel):
    qr_data: str
    active_id: str = ""
    course_id: str = ""
    class_id: str = ""
    proxy_friend_ids: list[int] = []


# ================================================================
# 辅助函数
# ================================================================

def get_client(token: str) -> ChaoxingClient:
    if token not in sessions:
        raise HTTPException(401, "未登录或 session 已过期")
    return sessions[token]


def get_or_create_user(db: Session, supernova_account: str, nickname: str = "") -> User:
    user = db.query(User).filter(User.supernova_account == supernova_account).first()
    if user is None:
        user = User(supernova_account=supernova_account, nickname=nickname or supernova_account)
        db.add(user)
        db.commit()
        db.refresh(user)
    elif nickname and user.nickname == user.supernova_account:
        user.nickname = nickname
        db.commit()
    return user


def require_db():
    if not db_available:
        raise HTTPException(503, "数据库服务不可用，请稍后重试")


def download_avatar(uid: str, url: str) -> str:
    """下载用户头像到 static/images/avatars/ 目录，返回本地路由"""
    import requests as req
    avatars_dir = static_dir / "images" / "avatars"
    avatars_dir.mkdir(parents=True, exist_ok=True)
    ext = ".jpg"
    if url:
        # 尝试从 URL 推断扩展名
        base = url.split("?")[0]
        if base.endswith(".png"):
            ext = ".png"
        elif base.endswith(".gif"):
            ext = ".gif"
    filepath = avatars_dir / f"{uid}{ext}"
    try:
        resp = req.get(url, timeout=15)
        if resp.ok:
            filepath.write_bytes(resp.content)
            return f"/static/images/avatars/{uid}{ext}"
    except Exception as e:
        log.warning("下载头像失败: %s", e)
    return ""


def save_user_session(db: Session, user_id: int, client: ChaoxingClient):
    """把超星会话 cookies 持久化到数据库"""
    cookies = client.session.cookies.get_dict()
    data = json.dumps(cookies, ensure_ascii=False)
    existing = db.query(UserSession).filter(UserSession.user_id == user_id).first()
    if existing:
        existing.cookies_json = data
        existing.uid = client.uid
        existing.name = client.name
    else:
        db.add(UserSession(
            user_id=user_id,
            cookies_json=data,
            uid=client.uid,
            name=client.name or "",
        ))
    db.commit()


def get_proxy_client(db: Session, user_id: int) -> ChaoxingClient | None:
    """从数据库加载用户的超星会话，返回可用客户端"""
    session_row = db.query(UserSession).filter(UserSession.user_id == user_id).first()
    if not session_row or not session_row.cookies_json:
        return None
    client = ChaoxingClient()
    try:
        cookies = json.loads(session_row.cookies_json)
        for key, value in cookies.items():
            client.session.cookies.set(key, value)
        client._uid = session_row.uid
        client._name = session_row.name
        client._logged_in = True
        return client
    except Exception:
        return None


# ================================================================
# 页面
# ================================================================

@app.get("/")
async def root():
    return FileResponse(static_dir / "index.html")


# ================================================================
# 超星登录（修改后：自动注册用户 + 返回 JWT）
# ================================================================

@app.post("/api/login")
async def api_login(phone: str = Query(...), password: str = Query(...)):
    client = ChaoxingClient()
    if not client.login(phone, password):
        raise HTTPException(400, "登录失败，请检查账号密码")

    token = uuid.uuid4().hex
    sessions[token] = client

    result: dict = {
        "ok": True,
        "token": token,
        "uid": client.uid,
        "name": client.name or phone,
    }

    if db_available:
        try:
            uid = client.uid
            if not uid:
                log.error("登录成功但 uid 为空，跳过入库: phone=%s", phone)
                return result

            # 获取账户详细信息（学校、头像）
            account_info = client.get_account_info()
            school = account_info.school or ""
            avatar_url = account_info.avatar or ""
            nickname = account_info.name or client.name or ""
            log.info("账户信息: nickname=%s school=%s avatar=%s", nickname, school, avatar_url)

            # 下载头像到本地
            local_avatar = ""
            if avatar_url and avatar_url.startswith("http"):
                local_avatar = download_avatar(uid, avatar_url)

            db = db_module.SessionLocal()
            user = get_or_create_user(db, uid, nickname)
            user.username = phone
            if school:
                user.school = school
            if local_avatar:
                user.avatar = local_avatar
            db.commit()
            log.info("用户入库成功: id=%s uid=%s nickname=%s avatar=%s", user.id, uid, user.nickname, user.avatar)

            # 持久化超星会话到数据库
            save_user_session(db, user.id, client)

            jwt_token = create_jwt(user.id)
            result["jwt"] = jwt_token
            result["user"] = {
                "id": user.id,
                "supernova_account": user.supernova_account,
                "nickname": user.nickname,
                "avatar": user.avatar,
                "school": user.school,
            }
            db.close()
        except Exception as e:
            log.error("自动注册用户失败: %s, uid=%s, name=%s", e, client.uid, client.name)

    return result


@app.post("/api/logout")
async def api_logout(token: str = Query(...)):
    sessions.pop(token, None)
    return {"ok": True}


@app.get("/api/session")
async def api_session(token: str = Query(...)):
    c = get_client(token)
    return {"ok": True, "uid": c.uid, "name": c.name}


# ================================================================
# 好友模块
# ================================================================

@app.get("/api/friends")
async def api_friends(
    token: str = Query(...),
    user_id: int = Depends(get_current_user_id),
):
    """获取好友列表"""
    require_db()
    get_client(token)
    db: Session = db_module.get_db()
    try:
        friendships = (
            db.query(Friendship, User)
            .join(User, Friendship.friend_id == User.id)
            .filter(Friendship.user_id == user_id)
            .all()
        )
        friends = [
            {
                "id": u.id,
                "supernova_account": u.supernova_account,
                "nickname": u.nickname,
                "location": u.location or "",
            }
            for _, u in friendships
        ]
        return {"ok": True, "friends": friends}
    finally:
        db.close()


@app.post("/api/friends")
async def api_add_friend(
    body: AddFriendRequest,
    token: str = Query(...),
    user_id: int = Depends(get_current_user_id),
):
    """添加好友"""
    require_db()
    get_client(token)
    db: Session = db_module.get_db()
    try:
        target_account = body.target_account.strip()
        if not target_account:
            raise HTTPException(400, "请输入账号")

        target = db.query(User).filter(User.username == target_account).first()
        if target is None:
            raise HTTPException(400, detail="该账号不存在")

        current_user = db.query(User).filter(User.id == user_id).first()
        if current_user and current_user.username == target_account:
            raise HTTPException(400, detail="不能添加自己为好友")

        existing = (
            db.query(Friendship)
            .filter(Friendship.user_id == user_id, Friendship.friend_id == target.id)
            .first()
        )
        if existing:
            raise HTTPException(400, detail="对方已是您的好友")

        db.add(Friendship(user_id=user_id, friend_id=target.id))
        db.add(Friendship(user_id=target.id, friend_id=user_id))
        db.commit()

        return {
            "ok": True,
            "friend": {
                "id": target.id,
                "supernova_account": target.supernova_account,
                "username":target.username,
                "nickname": target.nickname,
            },
        }
    finally:
        db.close()


@app.delete("/api/friends/{friend_id}")
async def api_delete_friend(
    friend_id: int,
    token: str = Query(...),
    user_id: int = Depends(get_current_user_id),
):
    """删除好友"""
    require_db()
    get_client(token)
    db: Session = db_module.get_db()
    try:
        db.query(Friendship).filter(
            Friendship.user_id == user_id, Friendship.friend_id == friend_id
        ).delete()
        db.query(Friendship).filter(
            Friendship.user_id == friend_id, Friendship.friend_id == user_id
        ).delete()
        db.commit()
        return {"ok": True}
    finally:
        db.close()


# ================================================================
# 课程与任务
# ================================================================

@app.get("/api/courses")
async def api_courses(token: str = Query(...)):
    c = get_client(token)
    courses = c.get_courses()
    return {
        "ok": True,
        "courses": [
            {
                "course_id": co.course_id,
                "class_id": co.class_id,
                "name": co.name,
                "teacher": co.teacher,
                "cover_url": co.cover_url,
            }
            for co in courses
        ],
    }


@app.get("/api/tasks/{course_id}/{class_id}")
async def api_tasks(course_id: str, class_id: str, token: str = Query(...)):
    c = get_client(token)

    course = Course(course_id=course_id, class_id=class_id, name="")
    tasks = c.get_sign_tasks(course, check_signed=True)

    type_name = {
        SignType.NORMAL: "normal", SignType.PHOTO: "photo",
        SignType.GESTURE: "gesture", SignType.LOCATION: "location",
        SignType.QRCODE: "qrcode", SignType.CODE: "code",
    }

    return {
        "ok": True,
        "tasks": [
            {
                "active_id": t.active_id,
                "name": t.name,
                "sign_type": type_name.get(t.sign_type, "normal"),
                "sign_type_label": t.sign_type.value,
                "status": t.status,
                "signed": getattr(t, "signed", False),
                "start_time": t.start_time,
                "end_time": t.end_time,
                "course_name": t.course_name,
            }
            for t in tasks
        ],
    }


# ================================================================
# 有签到活动的课程
# ================================================================

@app.get("/api/active-courses")
async def api_active_courses(token: str = Query(...)):
    """返回有活跃签到任务的课程列表，每个课程附带活跃任务数"""
    c = get_client(token)
    courses = c.get_courses()
    result = []
    for co in courses:
        try:
            tasks = c.get_sign_tasks(co, check_signed=False)
            active = [t for t in tasks if t.status == "active"]
            if active:
                result.append({
                    "course_id": co.course_id,
                    "class_id": co.class_id,
                    "name": co.name,
                    "teacher": co.teacher,
                    "cover_url": co.cover_url,
                    "active_count": len(active),
                    "tasks": [
                        {
                            "active_id": t.active_id,
                            "name": t.name,
                            "sign_type": t.sign_type.value,
                            "sign_type_label": t.sign_type.value,
                            "status": t.status,
                            "start_time": t.start_time,
                        }
                        for t in active
                    ],
                })
        except Exception:
            continue
    return {"ok": True, "courses": result}


# ================================================================
# 签到
# ================================================================

@app.post("/api/sign")
async def api_sign(
    token: str = Query(...),
    active_id: str = Query(...),
    course_id: str = Query(...),
    class_id: str = Query(...),
    sign_type: str = Query(...),
    enc: str = Query(""),
    sign_code: str = Query(""),
    gesture_code: str = Query(""),
    longitude: str = Query(""),
    latitude: str = Query(""),
    location_name: str = Query(""),
):
    c = get_client(token)

    type_map = {
        "normal": SignType.NORMAL, "photo": SignType.PHOTO,
        "gesture": SignType.GESTURE, "location": SignType.LOCATION,
        "qrcode": SignType.QRCODE, "code": SignType.CODE,
    }
    st = type_map.get(sign_type, SignType.NORMAL)

    task = SignTask(
        active_id=active_id,
        name="",
        course_name="",
        course_id=course_id,
        class_id=class_id,
        sign_type=st,
    )

    task = c.get_sign_detail(task)

    kwargs = {}
    if st == SignType.QRCODE and enc:
        kwargs["enc"] = enc
    if st == SignType.LOCATION:
        kwargs["longitude"] = longitude or default_location["longitude"]
        kwargs["latitude"] = latitude or default_location["latitude"]
        kwargs["location_name"] = location_name or default_location["name"]
    if st == SignType.CODE and sign_code:
        kwargs["code"] = sign_code
    if st == SignType.GESTURE and gesture_code:
        kwargs["gesture"] = gesture_code

    ok = c.sign(task, **kwargs)
    return {"ok": ok, "message": "签到成功" if ok else "签到失败"}


# ================================================================
# 二维码代签
# ================================================================

@app.post("/api/checkin/qrcode")
async def api_checkin_qrcode(
    body: QrcodeSignRequest,
    token: str = Query(...),
    user_id: int = Depends(get_current_user_id),
):
    """二维码代签：为自己和好友批量签到"""
    require_db()
    c = get_client(token)

    # 从二维码 URL 中提取所有参数
    qr_data = body.qr_data

    enc = ""
    m = re.search(r"enc=([a-zA-Z0-9_\-]+)", qr_data)
    if m:
        enc = m.group(1)

    active_id = body.active_id or ""
    course_id = body.course_id or ""
    class_id = body.class_id or ""

    # 从二维码 URL 中提取 enc
    m = re.search(r"enc=([A-Fa-f0-9]+)", qr_data)
    if m:
        enc = m.group(1)
    else:
        enc = qr_data.strip()

    if not enc:
        raise HTTPException(400, "无法解析二维码内容，缺少 enc 参数")

    task = SignTask(
        active_id=active_id,
        name="",
        course_name="",
        course_id=course_id,
        class_id=class_id,
        sign_type=SignType.QRCODE,
    )

    results = {"self": "failed", "proxy": []}

    # 为自己签到
    self_ok = c.sign(task, enc=enc)
    results["self"] = "success" if self_ok else "failed"

    # 为好友代签（使用好友自己的超星会话）
    if body.proxy_friend_ids:
        db: Session = db_module.get_db()
        try:
            for fid in body.proxy_friend_ids:
                friendship = (
                    db.query(Friendship)
                    .filter(Friendship.user_id == user_id, Friendship.friend_id == fid)
                    .first()
                )
                if not friendship:
                    results["proxy"].append({"friend_id": fid, "result": "无权代签"})
                    continue

                friend = db.query(User).filter(User.id == fid).first()
                if not friend:
                    results["proxy"].append({"friend_id": fid, "result": "好友不存在"})
                    continue

                # 获取好友的超星会话
                friend_client = get_proxy_client(db, fid)
                if not friend_client:
                    results["proxy"].append({
                        "friend_id": fid,
                        "supernova_account": friend.supernova_account,
                        "nickname": friend.nickname,
                        "result": "好友未登录过，无可用会话",
                    })
                    continue

                # 用好友自己的会话签到
                proxy_ok = friend_client.sign(task, enc=enc)
                proxy_result = "success" if proxy_ok else "failed"

                db.add(ProxyRecord(
                    user_id=user_id,
                    target_uid=friend.supernova_account,
                    active_id=task.active_id,
                    enc=enc,
                    result=proxy_result,
                ))
                db.commit()

                results["proxy"].append({
                    "friend_id": fid,
                    "supernova_account": friend.supernova_account,
                    "nickname": friend.nickname,
                    "result": proxy_result,
                })
        finally:
            db.close()

    return {"ok": True, "results": results}


# ================================================================
# 配置
# ================================================================

@app.get("/api/location_config")
async def api_location_config(token: str = Query(...)):
    get_client(token)
    return {"ok": True, "location": default_location}


@app.get("/api/config")
async def api_public_config():
    return {
        "amap_key": "你的高德地图key",
        "amap_version": "2.0",
    }


# ================================================================
# 启动
# ================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
