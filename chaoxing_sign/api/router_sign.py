"""签道路由 — /api/sign, /api/checkin/qrcode"""
from __future__ import annotations
import logging

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session

from .. import ChaoxingClient, SignType
from ..types import SignTask
from ..models import Friendship, User, ProxyRecord
from ..utils import extract_enc_from_qr
from ..auth.jwt import get_current_user_id
from .. import database as db_module

from . import deps
from .schemas import QrcodeSignRequest
from .router_auth import _get_proxy_client

from ..config import config as cfg

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["sign"])

default_location = cfg["location"]


@router.post("/sign")
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
    use_trilateration: str = Query("1"),
):
    c = deps.get_client(token)

    type_map = {
        "normal": SignType.NORMAL, "photo": SignType.PHOTO,
        "gesture": SignType.GESTURE, "location": SignType.LOCATION,
        "qrcode": SignType.QRCODE, "qrcode_location": SignType.QRCODE_LOCATION,
        "code": SignType.CODE,
    }
    st = type_map.get(sign_type, SignType.NORMAL)

    task = SignTask(
        active_id=active_id, name="", course_name="",
        course_id=course_id, class_id=class_id, sign_type=st,
    )
    task = c.get_sign_detail(task)

    kwargs = {}
    if st == SignType.QRCODE and enc:
        kwargs["enc"] = enc
    if st == SignType.LOCATION:
        kwargs["longitude"] = longitude or default_location["longitude"]
        kwargs["latitude"] = latitude or default_location["latitude"]
        kwargs["location_name"] = location_name or default_location["name"]
        kwargs["use_trilateration"] = use_trilateration
    if task.sign_type == SignType.QRCODE_LOCATION:
        kwargs["enc"] = enc
        kwargs["longitude"] = longitude or default_location["longitude"]
        kwargs["latitude"] = latitude or default_location["latitude"]
        kwargs["location_name"] = location_name or default_location["name"]
    if st == SignType.CODE and sign_code:
        kwargs["code"] = sign_code
    if st == SignType.GESTURE and gesture_code:
        kwargs["gesture"] = gesture_code

    ok = c.sign(task, **kwargs)
    return {"ok": ok, "message": "签到成功" if ok else "签到失败"}


@router.post("/checkin/qrcode")
async def api_checkin_qrcode(
    body: QrcodeSignRequest,
    token: str = Query(...),
    user_id: int = Depends(get_current_user_id),
):
    deps.require_db()
    c = deps.get_client(token)

    qr_data = body.qr_data
    enc = extract_enc_from_qr(qr_data)

    active_id = body.active_id or ""
    course_id = body.course_id or ""
    class_id = body.class_id or ""

    if not enc:
        raise HTTPException(400, "无法解析二维码内容，缺少 enc 参数")

    st = SignType.QRCODE_LOCATION if body.sign_type == "qrcode_location" else SignType.QRCODE

    task = SignTask(
        active_id=active_id, name="", course_name="",
        course_id=course_id, class_id=class_id, sign_type=st,
    )

    if st == SignType.QRCODE and active_id and course_id and class_id:
        try:
            task = c.get_sign_detail(task)
        except Exception:
            pass

    results = {"self": "failed", "proxy": []}

    sign_kwargs = {"enc": enc}
    if task.sign_type == SignType.QRCODE_LOCATION:
        sign_kwargs["longitude"] = body.longitude or default_location["longitude"]
        sign_kwargs["latitude"] = body.latitude or default_location["latitude"]
        sign_kwargs["location_name"] = body.location_name or default_location["name"]
        sign_kwargs["use_trilateration"] = body.use_trilateration

    self_ok = c.sign(task, **sign_kwargs)
    results["self"] = "success" if self_ok else "failed"

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

                friend_client = _get_proxy_client(db, fid)
                if not friend_client:
                    results["proxy"].append({
                        "friend_id": fid, "supernova_account": friend.supernova_account,
                        "nickname": friend.nickname, "result": "好友未登录过，无可用会话",
                    })
                    continue

                proxy_ok = friend_client.sign(task, **sign_kwargs)
                proxy_result = "success" if proxy_ok else "failed"

                db.add(ProxyRecord(
                    user_id=user_id, target_uid=friend.supernova_account,
                    active_id=task.active_id, enc=enc, result=proxy_result,
                ))
                db.commit()

                results["proxy"].append({
                    "friend_id": fid, "supernova_account": friend.supernova_account,
                    "nickname": friend.nickname, "result": proxy_result,
                })
        finally:
            db.close()

    return {"ok": True, "results": results}
