"""签道路由 — /api/sign, /api/checkin/qrcode"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session

from .. import ChaoxingClient, SignType
from ..types import SignTask
from ..models import Friendship, User, ProxyRecord
from ..utils import extract_enc_from_qr
from ..auth.jwt import get_current_user_id
from .. import database as db_module
from ..logging_config import get_logger

from . import deps
from .schemas import QrcodeSignRequest
from .router_auth import _get_proxy_client

from ..config import config as cfg

log = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["sign"])

default_location = cfg["location"]


@router.post("/sign")
async def api_sign(
    token: str = Query(...),
    active_id: str = Query(""),
    course_id: str = Query(""),
    class_id: str = Query(""),
    sign_type: str = Query(""),
    enc: str = Query(""),
    sign_code: str = Query(""),
    gesture_code: str = Query(""),
    longitude: str = Query(""),
    latitude: str = Query(""),
    location_name: str = Query(""),
    use_trilateration: str = Query("1"),
    friend_id: int = Query(0, description="代签好友的用户ID"),
    encrypted: str | None = Query(None),
):
    if encrypted:
        decrypted = deps.decrypt_query_payload(encrypted) or {}
        active_id = decrypted.get("active_id", active_id)
        course_id = decrypted.get("course_id", course_id)
        class_id = decrypted.get("class_id", class_id)
        sign_type = decrypted.get("sign_type", sign_type)
        enc = decrypted.get("enc", enc)
        sign_code = decrypted.get("sign_code", sign_code)
        gesture_code = decrypted.get("gesture_code", gesture_code)
        longitude = decrypted.get("longitude", longitude)
        latitude = decrypted.get("latitude", latitude)
        location_name = decrypted.get("location_name", location_name)
        use_trilateration = decrypted.get("use_trilateration", use_trilateration)
        friend_id = int(decrypted.get("friend_id", friend_id))

    if not active_id or not sign_type:
        raise HTTPException(400, "缺少签到参数")

    c = deps.get_client(token)

    # 代签：使用好友的 session
    log.info("签到请求: friend_id=%s uid=%s", friend_id, c.uid)
    if friend_id > 0:
        deps.require_db()
        db: Session = db_module.get_db()
        try:
            friend_client = _get_proxy_client(db, friend_id)
            if not friend_client:
                raise HTTPException(400, "好友无可用会话")
            c = friend_client
        finally:
            db.close()

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
        kwargs["use_trilateration"] = use_trilateration
    if st == SignType.CODE and sign_code:
        kwargs["code"] = sign_code
    if st == SignType.GESTURE and gesture_code:
        kwargs["gesture"] = gesture_code

    # 代签：提供 friend_id 时使用好友的 session 签到
    friend_id = Query(0)
    # HACK: fastapi Query() 不能在函数体中动态声明，这里从原始请求获取
    # 实际上 friend_id 需要从请求参数中提取，重读函数签名...
    # 让我们修改函数签名来支持 friend_id

    log.info("执行签到: uid=%s type=%s active_id=%s", c.uid, sign_type, active_id)
    ok, msg = c.sign(task, **kwargs)
    if ok:
        log.info("签到成功: uid=%s type=%s active_id=%s", c.uid, sign_type, active_id)
    else:
        log.warning("签到失败: uid=%s type=%s active_id=%s msg=%s", c.uid, sign_type, active_id, msg)
    return {"ok": ok, "message": msg}


@router.post("/checkin/qrcode")
async def api_checkin_qrcode(
    body: QrcodeSignRequest,
    token: str = Query(...),
    user_id: int = Depends(get_current_user_id),
):
    deps.require_db()
    c = deps.get_client(token)

    # 支持 encrypted 字段：解密后合并到 body 字段
    if body.encrypted:
        decrypted = deps.decrypt_body_payload({"encrypted": body.encrypted}) or {}
        qr_data = decrypted.get("qr_data", body.qr_data)
        active_id = decrypted.get("active_id", body.active_id or "")
        course_id = decrypted.get("course_id", body.course_id or "")
        class_id = decrypted.get("class_id", body.class_id or "")
        sign_type = decrypted.get("sign_type", body.sign_type)
        longitude = decrypted.get("longitude", body.longitude)
        latitude = decrypted.get("latitude", body.latitude)
        location_name = decrypted.get("location_name", body.location_name)
        use_trilateration = decrypted.get("use_trilateration", body.use_trilateration)
        proxy_friend_ids = decrypted.get("proxy_friend_ids", body.proxy_friend_ids)
    else:
        qr_data = body.qr_data
        active_id = body.active_id or ""
        course_id = body.course_id or ""
        class_id = body.class_id or ""
        sign_type = body.sign_type
        longitude = body.longitude
        latitude = body.latitude
        location_name = body.location_name
        use_trilateration = body.use_trilateration
        proxy_friend_ids = body.proxy_friend_ids

    enc = extract_enc_from_qr(qr_data)

    if not enc:
        log.error("无法解析二维码内容，缺少 enc 参数: qr_data=%s", qr_data[:100])
        raise HTTPException(400, "无法解析二维码内容，缺少 enc 参数")

    st = SignType.QRCODE_LOCATION if sign_type == "qrcode_location" else SignType.QRCODE

    task = SignTask(
        active_id=active_id, name="", course_name="",
        course_id=course_id, class_id=class_id, sign_type=st,
    )

    if st == SignType.QRCODE and active_id and course_id and class_id:
        try:
            task = c.get_sign_detail(task)
        except Exception as e:
            log.warning("获取签到详情失败: %s", e)

    results = {"self": "failed", "proxy": []}

    sign_kwargs = {"enc": enc}
    if task.sign_type == SignType.QRCODE_LOCATION:
        sign_kwargs["longitude"] = longitude or default_location["longitude"]
        sign_kwargs["latitude"] = latitude or default_location["latitude"]
        sign_kwargs["location_name"] = location_name or default_location["name"]
        sign_kwargs["use_trilateration"] = use_trilateration

    log.info("扫码签到: user_id=%d uid=%s enc=%s sign_type=%s", user_id, c.uid, enc, task.sign_type.value)
    self_ok, self_msg = c.sign(task, **sign_kwargs)
    results["self"] = "success" if self_ok else "failed"
    results["self_msg"] = self_msg
    log.info("本人签到结果: %s msg=%s", results["self"], self_msg)

    if proxy_friend_ids:
        log.info("开始代签: user_id=%d friend_ids=%s", user_id, proxy_friend_ids)
        db: Session = db_module.get_db()
        try:
            # 获取操作人账户信息
            action_user = db.query(User).filter(User.id == user_id).first()
            actionuser_name = action_user.supernova_account if action_user else str(user_id)

            for fid in proxy_friend_ids:
                friendship = (
                    db.query(Friendship)
                    .filter(Friendship.user_id == user_id, Friendship.friend_id == fid)
                    .first()
                )
                if not friendship:
                    log.warning("无权代签: user_id=%d friend_id=%d", user_id, fid)
                    results["proxy"].append({"friend_id": fid, "result": "无权代签", "message": "无权代签"})
                    continue

                friend = db.query(User).filter(User.id == fid).first()
                if not friend:
                    log.warning("好友不存在: friend_id=%d", fid)
                    results["proxy"].append({"friend_id": fid, "result": "好友不存在", "message": "好友不存在"})
                    continue

                friend_client = _get_proxy_client(db, fid)
                if not friend_client:
                    log.warning("好友无可用会话: friend_id=%d account=%s", fid, friend.supernova_account)
                    results["proxy"].append({
                        "friend_id": fid, "supernova_account": friend.supernova_account,
                        "nickname": friend.nickname, "result": "好友未登录过，无可用会话",
                        "message": "好友未登录过，无可用会话",
                    })
                    continue

                proxy_ok, proxy_msg = friend_client.sign(task, **sign_kwargs)
                proxy_result = "success" if proxy_ok else "failed"
                log.info("代签结果: actionuser=%s friend_id=%d target=%s result=%s msg=%s",
                         actionuser_name, fid, friend.supernova_account, proxy_result, proxy_msg)

                db.add(ProxyRecord(
                    user_id=user_id, target_uid=friend.supernova_account,
                    active_id=task.active_id, enc=enc, result=proxy_result,
                    actionuser=actionuser_name,
                    friendids=",".join(str(x) for x in proxy_friend_ids),
                ))
                db.commit()

                results["proxy"].append({
                    "friend_id": fid, "supernova_account": friend.supernova_account,
                    "nickname": friend.nickname, "result": proxy_result,
                    "message": proxy_msg,
                })
        finally:
            db.close()

    return {"ok": True, "results": results}
