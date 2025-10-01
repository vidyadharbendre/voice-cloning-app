# ================================
# FILE: run.py  (UPDATED)
# ================================
"""
Main entry point for the Voice Cloning Application.

Improvements:
- Attempt to reuse app.core.logging_config.setup_logging() when available.
- Validate minimal project layout (app/__init__.py) to give early, precise diagnostics.
- Slightly more conservative worker selection (cpus - 1, capped).
- Avoid duplicate file handlers if logging already configured.
- Clearer exception logging and exit semantics.
"""
import os
import sys
import logging
import traceback
from pathlib import Path
import multiprocessing
from logging.handlers import RotatingFileHandler
import uvicorn
from typing import Optional

# Put project root on sys.path so "import app" works reliably when running run.py directly.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# --- Basic runner logger (will be harmonized with app logging if available) ---
logger = logging.getLogger("voice_cloning.run")
logger.setLevel(logging.INFO)

# Console handler (always attach so early errors are visible)
if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch_formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s [%(threadName)s] %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    ch.setFormatter(ch_formatter)
    logger.addHandler(ch)

# Rotating file handler (placed in logs/run.log)
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "run.log"

def _attach_rotating_file_handler(path: Path) -> None:
    # Avoid registering multiple file handlers on repeated runs (useful during reload)
    for h in logger.handlers:
        if isinstance(h, RotatingFileHandler) and getattr(h, "baseFilename", "") == str(path):
            return
    fh = RotatingFileHandler(str(path), maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh_formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(module)s:%(lineno)d %(message)s", "%Y-%m-%d %H:%M:%S")
    fh.setFormatter(fh_formatter)
    logger.addHandler(fh)

_attach_rotating_file_handler(LOG_FILE)

# Try to import app logging configuration to unify formatting/handlers (non-fatal)
try:
    from app.core.logging_config import setup_logging  # type: ignore
    # Let the app configure logging early; if it adds handlers we won't duplicate later.
    setup_logging()
    logger.debug("Invoked app.core.logging_config.setup_logging()")
except Exception:
    logger.debug("app.core.logging_config.setup_logging() not available or failed; using local logger.", exc_info=True)

def _determine_workers(debug: bool) -> int:
    """Choose number of workers. Keep 1 in debug to allow reload; otherwise choose conservative default."""
    if debug:
        return 1
    try:
        cpus = multiprocessing.cpu_count()
        # conservative default: leave one CPU for system/other tasks
        workers = max(1, min(4, max(1, cpus - 1)))
        return workers
    except Exception:
        return 1

def validate_project_layout() -> Optional[str]:
    """
    Quick sanity checks that often cause import errors.
    Returns an error message string if a problem found, else None.
    """
    app_pkg = PROJECT_ROOT / "app"
    if not app_pkg.exists() or not app_pkg.is_dir():
        return f"Missing `app/` package at expected location: {app_pkg}"
    init_py = app_pkg / "__init__.py"
    if not init_py.exists():
        return f"Missing __init__.py in `app/` package; create an empty file at: {init_py}"
    return None

def main() -> None:
    """
    Programmatically start uvicorn with defensive import of the FastAPI `app`.
    Importing the app inside main() prevents circular import issues during module import time.
    """
    # Allow host/port/workers to be overridden with environment variables.
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    # Validate layout early to provide helpful diagnostics
    layout_err = validate_project_layout()
    if layout_err:
        logger.error("Project layout validation failed: %s", layout_err)
        logger.error("Please run from project root (the directory containing `app/`) and ensure app/__init__.py exists.")
        sys.exit(1)

    # Attempt to import settings if available to read debug flag; fall back to env var or default False
    debug = False
    try:
        from app.core.config import settings  # type: ignore
        debug = bool(getattr(settings, "debug", False))
        logger.debug("Loaded settings.debug=%s", debug)
    except Exception:
        logger.warning("Could not import app.core.config.settings — falling back to environment defaults.")
        logger.debug("settings import traceback:\n%s", traceback.format_exc())

    # Determine workers (env override takes precedence)
    try:
        workers_env = os.getenv("WORKERS")
        if workers_env:
            workers = int(workers_env)
        else:
            workers = _determine_workers(debug)
    except Exception:
        workers = 1

    # Now import the FastAPI app inside try/except to catch circular import or runtime errors
    try:
        # Importing here reduces risk of circular imports causing partially-initialized module errors.
        from app.main import app  # type: ignore
        logger.debug("Imported app.main:app successfully.")
    except Exception as exc:
        logger.error("Failed to import FastAPI `app` from app.main. Startup aborted.")
        logger.error("Error: %s", exc)
        logger.error("Traceback:\n%s", traceback.format_exc())
        logger.error(
            "Common causes:\n"
            " - You are running this file from a directory that is not the project root.\n"
            " - `app/` is missing __init__.py (so it's not a package).\n"
            " - Circular imports in app.main / route modules causing partially-initialized modules.\n\n"
            "Quick checks:\n"
            "  * Run from project root (the directory that contains the `app/` folder).\n"
            "  * Ensure `app/__init__.py` exists (can be empty).\n"
            "  * Inspect logs/run.log for earlier stack traces (model-loader may raise during import).\n"
        )
        # Exit with non-zero to signal failure to whatever supervisor started this process.
        sys.exit(1)

    # Build uvicorn args
    reload_flag = os.getenv("RELOAD", "true" if debug else "false").lower() in ("1", "true", "yes")
    log_level = os.getenv("LOG_LEVEL", "info").lower()

    logger.info(
        "Starting uvicorn server on %s:%d (reload=%s, workers=%d, log_level=%s)",
        host,
        port,
        reload_flag,
        workers,
        log_level,
    )

    # If multiple workers requested, warn operator about background tasks and model loads
    if workers > 1:
        logger.warning(
            "uvicorn configured with workers=%d. Ensure background tasks and model preloads are safe to run in multiple processes.",
            workers,
        )

    # Run uvicorn
    try:
        uvicorn.run(
            "app.main:app",
            host=host,
            port=port,
            reload=reload_flag,
            workers=workers,
            log_level=log_level,
        )
    except KeyboardInterrupt:
        logger.info("Shutdown requested (KeyboardInterrupt). Exiting gracefully.")
        raise
    except Exception as exc:
        logger.exception("Unexpected exception while running uvicorn: %s", exc)
        # Exit non-zero to indicate failure to orchestrator / systemd
        sys.exit(2)

if __name__ == "__main__":
    main()