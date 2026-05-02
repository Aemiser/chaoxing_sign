"""Redis 客户端 — 单例模式，用于签到任务缓存"""
from __future__ import annotations
import logging

import redis

from .config import config as cfg

logger = logging.getLogger(__name__)
_client: redis.Redis | None = None


def get_redis() -> redis.Redis | None:
    """获取 Redis 客户端（单例），连接失败返回 None"""
    global _client
    if _client is not None:
        return _client

    redis_cfg = cfg.get("redis", {})
    try:
        _client = redis.Redis(
            host=redis_cfg.get("host", "localhost"),
            port=int(redis_cfg.get("port", 6379)),
            db=int(redis_cfg.get("db", 0)),
            password=redis_cfg.get("password") or None,
            socket_connect_timeout=3,
            decode_responses=True,
        )
        _client.ping()
        logger.info("Redis 连接成功: %s:%d", redis_cfg.get("host"), redis_cfg.get("port"))
    except Exception as e:
        logger.warning("Redis 连接失败，缓存禁用: %s", e)
        _client = None

    return _client


# 缓存 key 前缀
CACHE_KEY_PREFIX = "sign_task"


def _task_key(course_id: str, class_id: str, active_id: str) -> str:
    return f"{CACHE_KEY_PREFIX}:{course_id}:{class_id}:{active_id}"


def cache_sign_task(task_item: dict, course_id: str, class_id: str) -> bool:
    """缓存单个活跃签到任务到 Redis（已结束的不缓存）。
    task_item: 完整的 API 返回项（含 nameTwo / status）
    """
    r = get_redis()
    if r is None:
        return False

    # 只缓存进行中的任务，已结束的不缓存
    if task_item.get("status") != 1:
        return False

    active_id = str(task_item.get("id", ""))
    if not active_id:
        return False

    key = _task_key(course_id, class_id, active_id)

    # 计算 TTL：从 nameTwo 提取结束时间
    ttl = _parse_ttl(task_item.get("nameTwo", ""))
    if ttl is None:
        # nameTwo 不存在时尝试用 startTime 推算（+24h）
        start_ts = task_item.get("startTime")
        if isinstance(start_ts, (int, float)) and start_ts > 0:
            ttl = max(3600, int(start_ts / 1000) + 86400 - _now())
        else:
            ttl = 86400  # 默认 1 天

    try:
        import json
        # 只存必要字段
        value = json.dumps({
            "active_id": active_id,
            "name": task_item.get("nameOne", ""),
            "raw_url": task_item.get("url", ""),
            "startTime": task_item.get("startTime", ""),
            "nameTwo": task_item.get("nameTwo", ""),
            "status": task_item.get("status", 1),
            "activeType": task_item.get("activeType", 2),
        }, ensure_ascii=False)
        r.setex(key, ttl, value)
        logger.debug("缓存签到任务: key=%s ttl=%ds", key, ttl)
        return True
    except Exception as e:
        logger.warning("缓存签到任务失败: %s", e)
        return False


def get_cached_tasks(course_id: str, class_id: str) -> list[dict]:
    """获取指定课程下所有缓存的签到任务"""
    r = get_redis()
    if r is None:
        return []

    pattern = f"{CACHE_KEY_PREFIX}:{course_id}:{class_id}:*"
    tasks = []
    try:
        for key in r.scan_iter(match=pattern, count=50):
            try:
                val = r.get(key)
                if val:
                    import json
                    tasks.append(json.loads(val))
            except Exception:
                pass
    except Exception as e:
        logger.warning("读取缓存签到任务失败: %s", e)

    return tasks


def _parse_ttl(name_two: str) -> int | None:
    """从 nameTwo（如 '结束时间：04-28 20:11'）解析结束时间，返回 TTL 秒数"""
    import re
    import datetime

    if not name_two:
        return None

    m = re.search(r'(\d{1,2})[-/](\d{1,2})\s+(\d{1,2}):(\d{2})', name_two)
    if not m:
        return None

    month, day, hour, minute = int(m[1]), int(m[2]), int(m[3]), int(m[4])
    now = datetime.datetime.now()
    end_dt = datetime.datetime(now.year, month, day, hour, minute)

    # 如果结束时间已过，可能是跨年，尝试下一年
    if end_dt < now:
        end_dt = datetime.datetime(now.year + 1, month, day, hour, minute)

    ttl = int((end_dt - now).total_seconds())
    return max(60, ttl)  # 最少 60 秒


def _now() -> int:
    import time
    return int(time.time())


def delete_cached_tasks(course_id: str, class_id: str):
    """删除指定课程的所有缓存任务（同步时调用）"""
    r = get_redis()
    if r is None:
        return
    try:
        pattern = f"{CACHE_KEY_PREFIX}:{course_id}:{class_id}:*"
        keys = list(r.scan_iter(match=pattern, count=100))
        if keys:
            r.delete(*keys)
    except Exception:
        pass
