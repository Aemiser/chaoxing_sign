"""好友路由 — /api/friends CRUD"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session

from ..models import Friendship, User
from ..auth.jwt import get_current_user_id
from .. import database as db_module

from . import deps
from .schemas import AddFriendRequest

router = APIRouter(prefix="/api", tags=["friends"])


@router.get("/friends")
async def api_friends(
    token: str = Query(...),
    user_id: int = Depends(get_current_user_id),
):
    deps.require_db()
    deps.get_client(token)
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
                "id": u.id, "supernova_account": u.supernova_account,
                "nickname": u.nickname, "avatar": u.avatar or "",
                "location": u.location or "",
            }
            for _, u in friendships
        ]
        return {"ok": True, "friends": friends}
    finally:
        db.close()


@router.post("/friends")
async def api_add_friend(
    body: AddFriendRequest,
    token: str = Query(...),
    user_id: int = Depends(get_current_user_id),
):
    deps.require_db()
    deps.get_client(token)

    # 支持 encrypted 字段解密
    target_account = body.target_account.strip()
    if body.encrypted:
        decrypted = deps.decrypt_body_payload({"encrypted": body.encrypted}) or {}
        target_account = decrypted.get("target_account", target_account).strip()

    db: Session = db_module.get_db()
    try:
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
        # db.add(Friendship(user_id=target.id, friend_id=user_id))
        db.commit()

        return {
            "ok": True,
            "friend": {
                "id": target.id, "supernova_account": target.supernova_account,
                "username": target.username, "nickname": target.nickname,
            },
        }
    finally:
        db.close()


@router.delete("/friends/{friend_id}")
async def api_delete_friend(
    friend_id: int,
    token: str = Query(...),
    user_id: int = Depends(get_current_user_id),
):
    deps.require_db()
    deps.get_client(token)
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
