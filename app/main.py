# ================================
# FILE: app/main.py  (REVISED - no uvicorn.run, with readiness + middlewares)
# ================================
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# Application routers / internals
from app.api.enhanced_routes import router as enhanced_router
from app.api.voice_profile_routes import router as voice_profile_router
from app.core.config import settings
from app.core.logging_config import setup_logging
# Avoid wildcard imports; import module so symbols are explicit where used.
import app.core.enhanced_exceptions as enhanced_exceptions
from app.core.exception_handlers import register_exception_handlers
from app.middleware.monitoring_middleware import MonitoringMiddleware
from app.middleware.rate_limit_middleware import RateLimitMiddleware
from app.core.background_tasks import background_tasks

# --- Setup logging (make logger available to lifespan) ---
# Prefer idempotent setup; if setup_logging is safe to call multiple times, this is fine.
setup_logging()  # configure handlers/formatters globally
logger = logging.getLogger(__name__)

# --- Create FastAPI application with enhanced configuration (lifespan attached shortly) ---
# We'll define the lifespan manager next and then create the app.
# --- Lifespan manager (startup/shutdown consolidated here) ---
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("🚀 Voice Cloning API starting up...")

    # Attach correlation id for this process (helps join logs in multi-process)
    correlation_id = f"proc-{os.getpid()}"
    app.state.correlation_id = correlation_id
    logger.debug("correlation_id set to %s", correlation_id)

    # initialize flags/state that readiness may check
    app.state.tts_preloaded = False
    app.state.voice_profile_service = None

    try:
        # Start background tasks (non-blocking)
        await background_tasks.start()
        logger.info("Background tasks started.")

        # Best-effort: create & cache a VoiceProfileService instance to avoid first-request latency.
        try:
            from app.services.voice_profile_service import VoiceProfileService  # type: ignore

            try:
                # Prefer constructor with no args, else try with storage dir
                svc = None
                try:
                    svc = VoiceProfileService()
                except TypeError:
                    # attempt constructor with storage dir if available
                    storage_dir = getattr(settings, "voice_profiles_dir", None) or getattr(settings, "VOICE_PROFILES_DIR", "voice_profiles")
                    svc = VoiceProfileService(storage_dir)
                app.state.voice_profile_service = svc
                logger.info("VoiceProfileService instantiated and cached on app.state")
            except Exception as e:
                logger.warning("Could not instantiate VoiceProfileService at startup (will fallback to lazy construction): %s", e)
        except Exception:
            # Service not available / import failed; that's OK — the factory will construct lazily when needed
            logger.debug("VoiceProfileService class not importable at startup; will construct lazily on first request.")

        # Optionally preload TTS model — failures are non-fatal
        # NOTE: preloading large models in multiple worker processes may be expensive.
        try:
            should_preload = getattr(settings, "preload_tts_on_startup", False)
        except Exception:
            should_preload = False

        if should_preload:
            # If user sets UVICORN_WORKERS or we programmatically set >1, preloading may repeat per worker.
            uvicorn_workers_env = os.getenv("UVICORN_WORKERS")
            logger.info("preload_tts_on_startup enabled; UVICORN_WORKERS=%s", uvicorn_workers_env)
            try:
                logger.info("Pre-loading TTS model (may be CPU/GPU heavy)...")
                # Import lazily to avoid import-time overhead when not preloading
                from app.services.tts_engine import XTTSTTSEngine  # type: ignore

                engine = XTTSTTSEngine()
                if asyncio.iscoroutinefunction(engine.initialize):
                    await engine.initialize()
                else:
                    engine.initialize()
                app.state.tts_preloaded = True
                logger.info("✅ TTS model pre-loaded successfully")
            except Exception as e:
                # Non-fatal: log and continue. Keeps API available.
                logger.exception("TTS model pre-loading failed (non-fatal): %s", e)

        logger.info("🎉 Voice Cloning API startup complete!")
    except Exception:
        logger.exception("❌ Startup failed")
        raise

    try:
        yield
    finally:
        logger.info("🛑 Voice Cloning API shutting down...")
        try:
            # stop background tasks gracefully
            await background_tasks.stop()
            logger.info("Background tasks stopped.")
        except Exception as e:
            logger.exception("Error while stopping background tasks: %s", e)
        logger.info("👋 Voice Cloning API shutdown complete!")


# --- Create FastAPI application with enhanced configuration ---
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Production-ready Voice Cloning and Text-to-Speech API using HuggingFace models",
    debug=settings.debug,
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Health", "description": "Health checks and system metrics"},
        {"name": "Voice Cloning", "description": "Voice cloning and text-to-speech operations"},
        {"name": "File Management", "description": "File upload, download, and management"},
    ],
)

# --- Security / operational middlewares added at app-level ---

# 1) Request size limiter (quick guard; respects settings.max_upload_bytes if present)
MAX_UPLOAD_BYTES = int(getattr(settings, "max_upload_bytes", 25 * 1024 * 1024))  # default 25 MB


@app.middleware("http")
async def limit_request_size_middleware(request: Request, call_next):
    """
    Simple guard against Content-Length exceeding configured max.
    Note: chunked uploads without Content-Length must be handled by the route-level streaming checks.
    """
    cl = request.headers.get("content-length")
    if cl:
        try:
            if int(cl) > MAX_UPLOAD_BYTES:
                return JSONResponse(status_code=413, content={"detail": "Payload too large"})
        except ValueError:
            # malformed header: continue and let downstream handle
            pass
    return await call_next(request)


# 2) Security headers middleware
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    # Recommended headers — set safely but avoid enabling HSTS by default if behind proxies — operators can tune.
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=()")
    return response


# --- Static files mounting ---
# Resolve static directory relative to this file for consistent behaviour in different working dirs
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = (BASE_DIR / "static").resolve()
if STATIC_DIR.exists() and STATIC_DIR.is_dir():
    # Mount static files under /static
    try:
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
        logger.info("Mounted static files at /static -> %s", STATIC_DIR)
    except Exception as exc:
        logger.exception("Failed to mount static files from %s: %s", STATIC_DIR, exc)
else:
    logger.warning("Static directory not found: %s. /static mount skipped.", STATIC_DIR)

# --- Add middleware (order matters) ---
# Monitoring first to measure time spent in downstream middlewares/handlers
app.add_middleware(MonitoringMiddleware)

# Rate limiting next
app.add_middleware(RateLimitMiddleware)

# CORS (tune in production)
allowed_origins = getattr(settings, "allowed_origins", ["*"])
if allowed_origins == ["*"]:
    logger.warning("CORS allowed_origins is set to '*' — consider tightening this in production.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Register centralized exception handlers ---
try:
    register_exception_handlers(app)
    logger.info("Registered exception handlers via app.core.exception_handlers.register_exception_handlers")
except Exception as exc:
    logger.exception("Failed to register centralized exception handlers: %s", exc)

    # fallback general handler so app still responds nicely
    async def _fallback_general_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error (fallback): %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "status_code": 500, "path": str(request.url.path)},
        )

    app.add_exception_handler(Exception, _fallback_general_handler)

# --- Include routers (after app created) ---
# Keep voice-profile router isolated under its own prefix to avoid accidental route overlap
try:
    app.include_router(voice_profile_router, prefix="/api/v1/voice-profiles", tags=["Voice Profiles"])
    app.include_router(enhanced_router, prefix="/api/v1", tags=["Voice Cloning", "Health", "File Management"])
    logger.info("Routers included successfully.")
except Exception as exc:
    logger.exception("Failed to include routers: %s", exc)
    raise


# --- Root / health endpoint ---
@app.get("/", tags=["Health"])
async def root():
    """Root endpoint with API information"""
    return {
        "message": "🎤 Voice Cloning API is running",
        "version": settings.version,
        "status": "operational",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "health_url": "/api/v1/health",
        "metrics_url": "/api/v1/metrics",
        "features": [
            "Voice Cloning with 3-10 seconds of audio",
            "Text-to-Speech in 17+ languages",
            "85-95% accuracy voice replication (approx.)",
            "Real-time processing",
            "Production-ready with monitoring",
        ],
        "rate_limits": getattr(settings, "rate_limits", {
            "upload": "10 per hour",
            "synthesize": "100 per hour",
            "clone": "50 per hour",
        }),
    }


# --- Readiness endpoint (useful for load-balancers / k8s) ---
@app.get("/ready", tags=["Health"])
async def readiness():
    """
    Simple readiness check:
      - background tasks running (best-effort)
      - TTS preloaded flag (if preloading configured)
      - voice_profile_service cached (best-effort)
    """
    ready = True
    details = {}

    # background tasks
    try:
        bg_running = getattr(background_tasks, "is_running", True)
        details["background_tasks_running"] = bool(bg_running)
        if not bg_running:
            ready = False
    except Exception:
        details["background_tasks_running"] = False
        ready = False

    # tts preload flag
    details["tts_preloaded"] = bool(getattr(app.state, "tts_preloaded", False))
    if getattr(settings, "preload_tts_on_startup", False) and not details["tts_preloaded"]:
        ready = False

    # voice profile service availability
    details["voice_profile_service_cached"] = bool(getattr(app.state, "voice_profile_service", None))
    # we don't force failure if service not cached; the factory can construct lazily

    status_code = 200 if ready else 503
    return JSONResponse(status_code=status_code, content={"ready": ready, "details": details})


# --- Serve voice recorder UI (safe, checks file existence) ---
VOICE_RECORDER_PATH = STATIC_DIR / "voice_recorder.html"

@app.get("/voice-recorder", response_class=FileResponse)
async def voice_recorder_interface():
    """
    Serve the voice recorder web interface (static/voice_recorder.html).
    Returns 404 JSON if missing to aid programmatic checks.
    """
    if VOICE_RECORDER_PATH.exists():
        return FileResponse(path=str(VOICE_RECORDER_PATH), filename="voice_recorder.html")
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Voice recorder UI not found. Expected at: {VOICE_RECORDER_PATH}"
    )

# Note: this module no longer starts the HTTP server directly.
# To run the server in development use either:
#   * python run.py          (if you keep and prefer your run.py entrypoint)
#   * uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# For production use Gunicorn + Uvicorn workers:
#   * gunicorn -k uvicorn.workers.UvicornWorker -w 4 --bind 0.0.0.0:8000 "app.main:app"