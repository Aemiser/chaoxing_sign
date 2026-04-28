#!/usr/bin/env python3
"""超星学习通签到 - FastAPI Web 服务"""
from __future__ import annotations
import uuid
import json
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from chaoxing_sign import ChaoxingClient, SignType
from chaoxing_sign.types import Course, SignTask

log = logging.getLogger("server")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="超星学习通签到", version="3.0")

# 静态文件
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Session 池: token → ChaoxingClient
sessions: dict[str, ChaoxingClient] = {}

# 加载默认位置配置
config_path = Path(__file__).parent / "config.json"
default_location = {"longitude": "116.404", "latitude": "39.915", "name": "北京市"}
if config_path.exists():
    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
        default_location.update(cfg.get("location", {}))
    except Exception:
        pass


def get_client(token: str) -> ChaoxingClient:
    if token not in sessions:
        raise HTTPException(401, "未登录或 session 已过期")
    return sessions[token]


# ================================================================
# API Endpoints
# ================================================================

@app.get("/")
async def root():
    return FileResponse(static_dir / "index.html")


@app.post("/api/login")
async def api_login(phone: str = Query(...), password: str = Query(...)):
    client = ChaoxingClient()
    if not client.login(phone, password):
        raise HTTPException(400, "登录失败，请检查账号密码")

    token = uuid.uuid4().hex
    sessions[token] = client
    return {
        "ok": True,
        "token": token,
        "uid": client.uid,
        "name": client.name or phone,
    }


@app.post("/api/logout")
async def api_logout(token: str = Query(...)):
    sessions.pop(token, None)
    return {"ok": True}


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
async def api_tasks(
    course_id: str,
    class_id: str,
    token: str = Query(...),
):
    c = get_client(token)
    from chaoxing_sign.types import Course

    course = Course(course_id=course_id, class_id=class_id, name="")
    tasks = c.get_sign_tasks(course)

    type_name = {SignType.NORMAL: "normal", SignType.PHOTO: "photo",
                 SignType.GESTURE: "gesture", SignType.LOCATION: "location",
                 SignType.QRCODE: "qrcode", SignType.CODE: "code"}

    return {
        "ok": True,
        "tasks": [
            {
                "active_id": t.active_id,
                "name": t.name,
                "sign_type": type_name.get(t.sign_type, "normal"),
                "sign_type_label": t.sign_type.value,
                "status": t.status,
                "start_time": t.start_time,
                "end_time": t.end_time,
                "course_name": t.course_name,
            }
            for t in tasks
        ],
    }


@app.post("/api/sign")
async def api_sign(
    token: str = Query(...),
    active_id: str = Query(...),
    course_id: str = Query(...),
    class_id: str = Query(...),
    sign_type: str = Query(...),
    enc: str = Query(""),
    longitude: str = Query(""),
    latitude: str = Query(""),
    location_name: str = Query(""),
):
    c = get_client(token)

    type_map = {"normal": SignType.NORMAL, "photo": SignType.PHOTO,
                "gesture": SignType.GESTURE, "location": SignType.LOCATION,
                "qrcode": SignType.QRCODE, "code": SignType.CODE}
    st = type_map.get(sign_type, SignType.NORMAL)

    task = SignTask(
        active_id=active_id,
        name="",
        course_name="",
        course_id=course_id,
        class_id=class_id,
        sign_type=st,
    )

    # 获取预签到详情（解析 preSign HTML）
    task = c.get_sign_detail(task)

    kwargs = {}
    if st == SignType.QRCODE and enc:
        kwargs["enc"] = enc
    if st == SignType.LOCATION:
        kwargs["longitude"] = longitude or default_location["longitude"]
        kwargs["latitude"] = latitude or default_location["latitude"]
        kwargs["location_name"] = location_name or default_location["name"]

    ok = c.sign(task, **kwargs)
    return {"ok": ok, "message": "签到成功" if ok else "签到失败"}


@app.get("/api/session")
async def api_session(token: str = Query(...)):
    c = get_client(token)
    return {"ok": True, "uid": c.uid, "name": c.name}


@app.get("/api/location_config")
async def api_location_config(token: str = Query(...)):
    """获取默认位置配置"""
    get_client(token)
    return {"ok": True, "location": default_location}


@app.get("/api/config")
async def api_public_config():
    """公开配置 - AMap key 等"""
    return {
        "amap_key": "你的高德地图key",  # 用户需自行替换
        "amap_version": "2.0",
    }


# ================================================================
# 启动
# ================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
