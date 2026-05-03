"""课程/任务路由 — /api/courses, /api/tasks, /api/active-courses"""
from __future__ import annotations
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests as req
from bs4 import BeautifulSoup
from fastapi import APIRouter, Query
from sqlalchemy.orm import Session

from .. import SignType
from ..redis_client import delete_cached_tasks
from ..types import Course
from ..models import CourseRecord
from ..logging_config import get_logger
from .. import database as db_module
from . import deps

log = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["courses"])


def _query_course_active(cookies: dict, course) -> tuple:
    """单个课程活跃任务查询（线程安全，使用独立 session）"""
    from ..redis_client import cache_sign_task, update_cached_task_location

    s = req.Session()
    s.headers.update({
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 13; SM-G981B Build/TP1A.220624.014) com.chaoxing.mobile/ChaoXingStudy_3.0_48_20231201_android",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.8",
    })
    for k, v in cookies.items():
        s.cookies.set(k, v)

    resp = s.get(
        "https://mobilelearn.chaoxing.com/ppt/activeAPI/taskactivelist",
        params={"courseId": course.course_id, "classId": course.class_id, "fid": "0", "showNotStartedActive": "0"},
        timeout=15,
    )
    data = resp.json()
    active = []
    for item in data.get("activeList", []):
        try:
            if int(item.get("activeType", 0)) != 2:
                continue
        except (ValueError, TypeError):
            continue
        if item.get("status") != 1:
            continue
        name = item.get("nameOne", "")
        st_raw = SignType.from_chinese(name).value
        raw_url = item.get("url", "")
        active_id = str(item.get("id", ""))
        if not active_id and "activePrimaryId=" in raw_url:
            m = re.search(r"activePrimaryId=(\d+)", raw_url)
            if m:
                active_id = m.group(1)

        location_name = ""
        if st_raw in ("qrcode", "location") and raw_url:
            try:
                resp2 = s.get(raw_url, timeout=10)
                soup = BeautifulSoup(resp2.text, "lxml")
                el = soup.select_one("#ifopenAddress")
                if el and el.get("value") == "1":
                    st_raw = "qrcode_location" if st_raw == "qrcode" else "location_named"
                    loc_el = soup.select_one("#locationText")
                    if loc_el and loc_el.get("value"):
                        location_name = loc_el.get("value")
                    log.info("检测到指定地点签到: %s → %s", name, active_id)
            except Exception:
                pass

        # 清空指定课程的缓存
        delete_cached_tasks(course.course_id, course.class_id)

        # 写入 Redis 缓存
        cache_sign_task(item, course.course_id, course.class_id)

        # 如果有指定位置名称，更新缓存
        if location_name and active_id:
            update_cached_task_location(
                course.course_id, course.class_id, active_id, location_name
            )

        active.append({
            "active_id": active_id, "name": name, "sign_type": st_raw,
            "sign_type_label": st_raw, "status": "active",
            "signed": False,
            "start_time": str(item.get("startTime", "")),
            "end_time": str(item.get("endTime", "")),
            "course_name": course.name,
            "location_name": location_name,
        })
    return (course, active)


@router.get("/courses")
async def api_courses(
    token: str = Query(...),
    source: int = Query(0, description="0=从数据库读取, 1=从超星API获取并更新数据库"),
    user_id: int = Query(0, description="用户ID，source=0时需要"),
    encrypted: str | None = Query(None),
):
    if encrypted:
        decrypted = deps.decrypt_query_payload(encrypted) or {}
        source = int(decrypted.get("source", source))
        user_id = int(decrypted.get("user_id", user_id))

    deps.get_client(token)

    if source == 0:
        if not user_id:
            return {"ok": True, "courses": [], "source": "db", "error": "缺少 user_id"}
        db: Session = db_module.get_db()
        try:
            records = (
                db.query(CourseRecord)
                .filter(CourseRecord.user_id == user_id)
                .order_by(CourseRecord.updated_at.desc())
                .all()
            )
            courses = [
                {
                    "course_id": r.course_id,
                    "class_id": r.class_id,
                    "name": r.name,
                    "teacher": r.teacher,
                    "cover_url": r.cover_url,
                }
                for r in records
            ]
            log.info("从数据库读取课程: user_id=%d count=%d", user_id, len(courses))
            return {"ok": True, "courses": courses, "source": "db"}
        finally:
            db.close()

    # source=1: 从超星 API 获取并更新数据库
    c = deps.get_client(token)
    courses = c.get_courses()
    if courses and user_id:
        db: Session = db_module.get_db()
        try:
            for course in courses:
                existing = (
                    db.query(CourseRecord)
                    .filter(
                        CourseRecord.user_id == user_id,
                        CourseRecord.course_id == course.course_id,
                        CourseRecord.class_id == course.class_id,
                    )
                    .first()
                )
                if existing:
                    existing.name = course.name
                    existing.teacher = course.teacher
                    existing.cover_url = course.cover_url
                else:
                    db.add(CourseRecord(
                        user_id=user_id,
                        course_id=course.course_id,
                        class_id=course.class_id,
                        name=course.name,
                        teacher=course.teacher,
                        cover_url=course.cover_url,
                    ))
            db.commit()
            log.info("课程列表已同步: user_id=%d count=%d", user_id, len(courses))
        except Exception as e:
            log.error("同步课程列表失败: %s", e)
        finally:
            db.close()

    return {
        "ok": True,
        "courses": [
            {
                "course_id": co.course_id, "class_id": co.class_id,
                "name": co.name, "teacher": co.teacher, "cover_url": co.cover_url,
            }
            for co in courses
        ],
        "source": "api",
    }


def _task_to_dict(t, display_type_fn) -> dict:
    return {
        "active_id": t.active_id, "name": t.name,
        "sign_type": display_type_fn(t), "sign_type_label": t.sign_type.value,
        "status": t.status, "signed": getattr(t, "signed", False),
        "start_time": t.start_time, "end_time": t.end_time,
        "course_name": t.course_name,
        "location_name": getattr(t, "location_name", ""),
    }


def _display_type_st(st: SignType, location_name: str = "") -> str:
    """返回前端显示的 sign_type（基于 SignType + location_name）。"""
    if st in (SignType.QRCODE, SignType.QRCODE_LOCATION):
        return "qrcode_location"
    if st == SignType.LOCATION:
        if location_name:
            return "location_named"
        return "location"
    return st.value


def _display_type(t):
    """返回前端显示的 sign_type（基于 SignTask 对象）。"""
    return _display_type_st(t.sign_type, getattr(t, "location_name", ""))


@router.get("/tasks/{course_id}/{class_id}")
async def api_tasks(course_id: str, class_id: str, token: str = Query(...),
                    sync: int = Query(0, description="1=强制同步，跳过缓存直接请求超星 API"),
                    encrypted: str | None = Query(None)):
    if encrypted:
        decrypted = deps.decrypt_query_payload(encrypted) or {}
        course_id = decrypted.get("course_id", course_id)
        class_id = decrypted.get("class_id", class_id)
        sync = int(decrypted.get("sync", sync))

    from ..redis_client import get_cached_tasks, delete_cached_tasks

    # sync=1：清除缓存，强制请求 API
    if sync:
        delete_cached_tasks(course_id, class_id)
    else:
        # 缓存优先：从 Redis 读取各任务独立缓存
        cached = get_cached_tasks(course_id, class_id)
        if cached:
            task_dicts = []
            for it in cached:
                st = SignType.from_chinese(it.get("name", ""))
                task_dicts.append({
                    "active_id": str(it.get("active_id", "")),
                    "name": it.get("name", ""),
                    "sign_type": _display_type_st(st),
                    "sign_type_label": st.value,
                    "status": "active",
                    "signed": False,
                    "start_time": str(it.get("startTime", "")),
                    "end_time": "",
                    "course_name": "",
                    "location_name": it.get("location_name", ""),
                })
            return {"ok": True, "tasks": task_dicts, "cached": True}

    # 缓存未命中：请求超星 API（get_sign_tasks 内部会逐任务缓存）
    c = deps.get_client(token)
    course = Course(course_id=course_id, class_id=class_id, name="")
    tasks = c.get_sign_tasks(course, check_signed=True)

    # 并行获取签到详情（QRCODE / LOCATION），大幅减少等待时间
    detail_tasks = [t for t in tasks if t.sign_type in (SignType.QRCODE, SignType.LOCATION)]
    if detail_tasks:
        c.get_sign_details_batch(detail_tasks)

    return {"ok": True, "tasks": [_task_to_dict(t, _display_type) for t in tasks]}


@router.get("/active-courses")
async def api_active_courses(token: str = Query(...)):
    c = deps.get_client(token)
    courses = c.get_courses()
    if not courses:
        return {"ok": True, "courses": []}

    cookies = c.session.cookies.get_dict()
    result = []

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_query_course_active, cookies, co): co for co in courses}
        for fut in as_completed(futures):
            try:
                course, active = fut.result()
            except Exception:
                continue
            if not active:
                continue
            result.append({
                "course_id": course.course_id, "class_id": course.class_id,
                "name": course.name, "teacher": course.teacher,
                "cover_url": course.cover_url, "active_count": len(active),
                "tasks": active,
            })

    return {"ok": True, "courses": result}
