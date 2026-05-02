"""配置/页面路由 — /, /health, /api/location_config, /api/config"""
from __future__ import annotations
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from ..config import config as cfg

from . import deps

router = APIRouter(tags=["config"])
default_location = cfg["location"]
static_dir = Path(__file__).parent.parent.parent / "static"


@router.get("/")
async def root():
    return FileResponse(static_dir / "index.html")


@router.get("/api/location_config")
async def api_location_config(token: str = Query(...)):
    deps.get_client(token)
    return {"ok": True, "location": default_location}


@router.get("/api/config")
async def api_public_config():
    return {
        "amap_key": cfg.get("amap_key", ""),
        "amap_version": cfg.get("amap_version", "2.0"),
        "tmap_key": cfg.get("tmap_key", ""),
        "sign": cfg.get("sign", {}),
    }


@router.get("/health")
async def health_check():
    sm = deps.session_manager
    return {
        "status": "ok",
        "sessions": len(sm) if sm else 0,
        "db_available": sm is not None,
    }
