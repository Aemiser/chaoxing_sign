"""课程/任务路由 — /api/courses, /api/tasks, /api/active-courses"""
from __future__ import annotations
import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests as req
from bs4 import BeautifulSoup
from fastapi import APIRouter, Query

from .. import SignType
from ..types import Course
from . import deps

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["courses"])


def _query_course_active(cookies: dict, course) -> tuple:
    """单个课程活跃任务查询（线程安全，使用独立 session）"""
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

        if st_raw == "qrcode" and raw_url:
            try:
                resp2 = s.get(raw_url, timeout=10)
                soup = BeautifulSoup(resp2.text, "lxml")
                el = soup.select_one("#ifopenAddress")
                if el and el.get("value") == "1":
                    st_raw = "qrcode_location"
                    logging.getLogger(__name__).info("检测到指定位置二维码签到: %s", active_id)
            except Exception:
                pass

        active.append({
            "active_id": active_id, "name": name, "sign_type": st_raw,
            "sign_type_label": st_raw, "status": "active",
            "start_time": str(item.get("startTime", "")),
            "end_time": str(item.get("endTime", "")),
        })
    return (course, active)


@router.get("/courses")
async def api_courses(token: str = Query(...)):
    c = deps.get_client(token)
    courses = c.get_courses()
    return {
        "ok": True,
        "courses": [
            {
                "course_id": co.course_id, "class_id": co.class_id,
                "name": co.name, "teacher": co.teacher, "cover_url": co.cover_url,
            }
            for co in courses
        ],
    }


@router.get("/tasks/{course_id}/{class_id}")
async def api_tasks(course_id: str, class_id: str, token: str = Query(...)):
    c = deps.get_client(token)
    course = Course(course_id=course_id, class_id=class_id, name="")
    tasks = c.get_sign_tasks(course, check_signed=True)

    for t in tasks:
        if t.sign_type == SignType.QRCODE:
            try:
                c.get_sign_detail(t)
            except Exception:
                pass

    return {
        "ok": True,
        "tasks": [
            {
                "active_id": t.active_id, "name": t.name,
                "sign_type": t.sign_type.value, "sign_type_label": t.sign_type.value,
                "status": t.status, "signed": getattr(t, "signed", False),
                "start_time": t.start_time, "end_time": t.end_time,
                "course_name": t.course_name,
            }
            for t in tasks
        ],
    }


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
