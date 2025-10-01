# app/api/enhanced_routes.py
import time
import logging
from typing import Dict, Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.health_checker import check_model_health
from app.services.tts_engine import XTTSTTSEngine
from app.status import status as global_status  # optional — adapt if unavailable

logger = logging.getLogger(__name__)
router = APIRouter()

# Shared singleton engine (load once and reuse)
_engine = XTTSTTSEngine()


@router.get("/health", name="health-check")
async def health(request: Request) -> JSONResponse:
    """
    Health endpoint. Note: router will typically be included with prefix="/api/v1"
    so final path becomes "/api/v1/health".
    """
    start_ts = time.time()
    request_id = getattr(request.state, "request_id", None)
    try:
        # Lazily initialize engine (initialize is idempotent)
        if not _engine.is_initialized():
            logger.info("Initializing shared TTS engine for health check", extra={"request_id": request_id})
            await _engine.initialize()

        result: Dict[str, Any] = await check_model_health(_engine)
        ok = bool(result.get("ok", False))
        status_str = "healthy" if ok else "unhealthy"
        http_status = 200 if ok else 503

        payload = {
            "status": status_str,
            "timestamp": time.time(),
            "uptime": getattr(global_status, "service_uptime", 0) if global_status is not None else 0,
            "version": settings.version,
            "details": {
                "model": {
                    "loaded": ok,
                    "last_check": getattr(global_status, "last_model_check", None) if global_status is not None else None,
                    "reason": result.get("reason"),
                },
            },
        }

        logger.info(
            "Health check completed",
            extra={"request_id": request_id, "path": request.url.path, "status": status_str, "duration_s": time.time() - start_ts},
        )
        return JSONResponse(status_code=http_status, content=payload)

    except Exception as exc:
        logger.exception("Health endpoint unexpected error", exc_info=exc, extra={"request_id": request_id})
        problem = {
            "type": "about:blank",
            "title": "Health check failure",
            "status": 500,
            "detail": str(exc),
            "instance": request.url.path,
        }
        return JSONResponse(status_code=500, content=problem, media_type="application/problem+json")
