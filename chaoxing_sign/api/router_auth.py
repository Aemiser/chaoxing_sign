"""认证路由 — /api/login, /api/logout, /api/session"""
from __future__ import annotations
import uuid
import time
import json
import threading
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import Session

from .. import ChaoxingClient
from ..auth.jwt import create_jwt
from ..auth.session import SessionManager
from .. import database as db_module
from ..models import User, UserSession
from ..logging_config import get_logger

from . import deps

log = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["auth"])

_session_manager: SessionManager | None = None


def init(sm: SessionManager):
    global _session_manager
    _session_manager = sm


def _mask_phone(phone: str) -> str:
    if len(phone) >= 8:
        return f"{phone[:3]}****{phone[-4:]}"
    return f"{phone[:1]}****" if len(phone) > 1 else "***"


def _download_avatar(uid: str, url: str) -> str:
    """下载用户头像到 static/images/avatars/ 目录，返回本地路由"""
    import requests as req
    from pathlib import Path

    static_dir = Path(__file__).parent.parent.parent / "static"

    if url.startswith("//"):
        url = "https:" + url
    if url and not url.startswith("/"):
        parsed = urlparse(url)
        allowed_hosts = {"chaoxing.com", "chaoxing.com.cn", "xuexitong.com"}
        host_ok = any(
            parsed.hostname and (parsed.hostname == h or parsed.hostname.endswith("." + h))
            for h in allowed_hosts
        )
        if not host_ok:
            log.warning("头像下载被阻止（非白名单域名）: %s", url[:120])
            return ""

    avatars_dir = static_dir / "images" / "avatars"
    avatars_dir.mkdir(parents=True, exist_ok=True)

    ext = ".jpg"
    if url:
        base = url.split("?")[0]
        if base.endswith(".png"):
            ext = ".png"
        elif base.endswith(".gif"):
            ext = ".gif"

    filepath = avatars_dir / f"{uid}{ext}"
    for old_ext in (".jpg", ".png", ".gif"):
        if old_ext != ext:
            try:
                (avatars_dir / f"{uid}{old_ext}").unlink(missing_ok=True)
            except Exception:
                pass

    try:
        headers = {
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 13; SM-G981B Build/TP1A.220624.014) com.chaoxing.mobile/ChaoXingStudy_3.0_48_20231201_android",
            "Referer": "https://i.chaoxing.com/",
        }
        resp = req.get(url, timeout=15, headers=headers)
        if resp.ok:
            filepath.write_bytes(resp.content)
            return f"/static/images/avatars/{uid}{ext}"
    except Exception as e:
        log.warning("下载头像失败: %s", e)
    return ""


def _save_user_session(db: Session, user_id: int, client: ChaoxingClient):
    cookies = client.session.cookies.get_dict()
    data = json.dumps(cookies, ensure_ascii=False)
    existing = db.query(UserSession).filter(UserSession.user_id == user_id).first()
    if existing:
        existing.cookies_json = data
        existing.uid = client.uid
        existing.name = client.name
    else:
        db.add(UserSession(
            user_id=user_id, cookies_json=data,
            uid=client.uid, name=client.name or "",
        ))
    db.commit()


def _get_proxy_client(db: Session, user_id: int) -> ChaoxingClient | None:
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


def _get_or_create_user(db: Session, supernova_account: str, nickname: str = "") -> User:
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


@router.post("/login")
async def api_login(phone: str = Query(...), password: str = Query(...)):
    if _session_manager is None:
        raise HTTPException(503, "服务未就绪")
    deps.require_db()
    db_available = True

    # 快速路径：尝试复用已保存的会话
    db = None
    try:
        db = db_module.SessionLocal()
        user = db.query(User).filter(User.username == phone).first()
        if user:
            saved = _get_proxy_client(db, user.id)
            if saved:
                try:
                    saved.session.get("https://i.chaoxing.com/base", timeout=5)
                    token = uuid.uuid4().hex
                    _session_manager.add(token, saved)
                    _save_user_session(db, user.id, saved)
                    jwt_token = create_jwt(user.id)
                    log.info("复用已保存会话: phone=%s uid=%s", _mask_phone(phone), saved.uid)
                    return {
                        "ok": True, "token": token, "uid": saved.uid,
                        "name": saved.name or phone, "jwt": jwt_token,
                        "user": {
                            "id": user.id, "supernova_account": user.supernova_account,
                            "nickname": user.nickname, "avatar": user.avatar or "",
                            "school": user.school or "",
                        },
                    }
                except Exception:
                    pass
    except Exception:
        pass
    finally:
        if db:
            try: db.close()
            except Exception: pass

    # 正常登录路径
    client = ChaoxingClient()
    if not client.login(phone, password, skip_user_info=True):
        raise HTTPException(400, "登录失败，请检查账号密码")

    token = uuid.uuid4().hex
    _session_manager.add(token, client)

    result: dict = {"ok": True, "token": token, "uid": client.uid, "name": client.name or phone}

    try:
        uid = client.uid
        if not uid:
            log.error("登录成功但 uid 为空，跳过入库: phone=%s", _mask_phone(phone))
            return result

        db = db_module.SessionLocal()
        existing = db.query(User).filter(User.supernova_account == uid).first()

        if existing:
            user = existing
            user.username = phone
            db.commit()
            _save_user_session(db, user.id, client)
            # 后台更新用户信息
            def _bg_enrich():
                try:
                    account_info = client.get_account_info()
                    school = account_info.school or ""
                    avatar_url = account_info.avatar or ""
                    nickname = account_info.name or client.name or ""
                    local_avatar = ""
                    if avatar_url and (avatar_url.startswith("http") or avatar_url.startswith("//")):
                        local_avatar = _download_avatar(uid, avatar_url)
                    db2 = db_module.SessionLocal()
                    u = _get_or_create_user(db2, uid, nickname)
                    if school: u.school = school
                    if local_avatar: u.avatar = local_avatar
                    if nickname and u.nickname == u.supernova_account: u.nickname = nickname
                    db2.commit()
                    db2.close()
                except Exception as e:
                    log.warning("后台更新用户信息失败: %s", e)
            threading.Thread(target=_bg_enrich, daemon=True).start()
        else:
            account_info = client.get_account_info()
            nickname = account_info.name or client.name or phone
            school = account_info.school or ""
            avatar_url = account_info.avatar or ""
            log.info("新用户注册: phone=%s uid=%s nickname=%s school=%s",
                     _mask_phone(phone), uid, nickname, school)
            user = _get_or_create_user(db, uid, nickname)
            user.username = phone
            if school: user.school = school
            db.commit()
            _save_user_session(db, user.id, client)
            if avatar_url and (avatar_url.startswith("http") or avatar_url.startswith("//")):
                def _dl_avatar():
                    try:
                        db3 = db_module.SessionLocal()
                        local = _download_avatar(uid, avatar_url)
                        if local:
                            uu = db3.query(User).filter(User.id == user.id).first()
                            if uu:
                                uu.avatar = local
                                db3.commit()
                        db3.close()
                    except Exception as e:
                        log.warning("后台头像下载失败: %s", e)
                threading.Thread(target=_dl_avatar, daemon=True).start()

        jwt_token = create_jwt(user.id)
        result["jwt"] = jwt_token
        result["user"] = {
            "id": user.id, "supernova_account": user.supernova_account,
            "nickname": user.nickname, "avatar": user.avatar or "",
            "school": user.school or "",
        }
        db.close()
    except Exception as e:
        log.error("自动注册用户失败: %s, uid=%s, name=%s", e, client.uid, client.name)

    return result


@router.post("/logout")
async def api_logout(token: str = Query(...)):
    if _session_manager:
        _session_manager.remove(token)
    return {"ok": True}


@router.get("/session")
async def api_session(token: str = Query(...)):
    c = deps.get_client(token)
    return {"ok": True, "uid": c.uid, "name": c.name}
