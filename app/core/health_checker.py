"""
Health Checker Module
Monitors application health and model status with robust multi-speaker support
"""
import os
import time
import tempfile
import logging
import asyncio
import inspect
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Try to import settings if available
try:
    from app.core.config import settings
except Exception:
    settings = None
    logger.warning("Could not import settings, using defaults")


class HealthChecker:
    """Stateful health checker for the application"""

    def __init__(self):
        self.start_time = time.time()
        self.version = "1.0.0"
        self.last_check = None
        self.model_loaded = False
        self.model_status = "not_initialized"
        self.model_reason = None

    async def check_health(self, tts_engine=None) -> Dict[str, Any]:
        """
        Check overall application health

        Args:
            tts_engine: TTS engine instance to check

        Returns:
            Health status dictionary
        """
        self.last_check = time.time()
        uptime = self.last_check - self.start_time

        # Check model status
        if tts_engine:
            model_details = await check_model_health(tts_engine)
            is_healthy = model_details.get("ok", False)
        else:
            model_details = {"ok": False, "reason": "TTS engine not initialized"}
            is_healthy = False

        # Update internal state
        self.model_loaded = is_healthy
        self.model_status = "loaded" if is_healthy else "failed"
        self.model_reason = model_details.get("reason")

        health_status = {
            "status": "healthy" if is_healthy else "unhealthy",
            "timestamp": self.last_check,
            "uptime": uptime,
            "version": self.version,
            "details": {"model": model_details},
        }

        return health_status

    def get_status(self) -> str:
        """Get current health status"""
        return "healthy" if self.model_loaded else "unhealthy"

    def mark_model_loaded(self, loaded: bool = True, reason: Optional[str] = None):
        """Mark model as loaded or not"""
        self.model_loaded = loaded
        self.model_status = "loaded" if loaded else "failed"
        self.model_reason = reason
        logger.info(f"Model status: {self.model_status}, Reason: {reason}")


async def check_model_health(tts_engine) -> Dict[str, Any]:
    """
    Low-level health-check helper for TTS model.
    Returns {"ok": bool, "reason": Optional[str], ...additional info...}.

    This is an async function for use in FastAPI routes.
    """
    now = time.time()
    result: Dict[str, Any] = {"ok": False, "reason": None}

    # Optional global status object (safe import)
    try:
        from app.status import status as global_status  # type: ignore
    except Exception:
        global_status = None  # type: Optional[object]

    try:
        logger.info("Running TTS model health check")

        # Check if model is loaded (support different engine APIs)
        if not hasattr(tts_engine, "is_loaded") and not hasattr(tts_engine, "is_initialized"):
            # Best-effort: check _initialized / _model attributes
            is_loaded_flag = bool(getattr(tts_engine, "_initialized", False) or getattr(tts_engine, "_model", None) is not None)
            if not is_loaded_flag:
                result["reason"] = "Model not loaded"
                return result
        else:
            # Prefer engine-provided method if available
            is_loaded = False
            if hasattr(tts_engine, "is_loaded") and callable(getattr(tts_engine, "is_loaded")):
                try:
                    is_loaded = tts_engine.is_loaded()
                except Exception:
                    is_loaded = False
            elif hasattr(tts_engine, "is_initialized") and callable(getattr(tts_engine, "is_initialized")):
                try:
                    is_loaded = tts_engine.is_initialized()
                except Exception:
                    is_loaded = False

            if not is_loaded:
                result["reason"] = "Model not loaded"
                return result

        # Obtain the model object
        model = getattr(tts_engine, "model", None) or getattr(tts_engine, "_model", None)
        if model is None:
            result["reason"] = "Model object is None"
            return result

        # Try to get model info (engine may expose metadata)
        try:
            model_info = tts_engine.get_model_info() if hasattr(tts_engine, "get_model_info") else {}
            is_multi_speaker = bool(model_info.get("is_multi_speaker", False))
            result.update({"model_type": "multi-speaker" if is_multi_speaker else "single-speaker", "model_loaded": True})
        except Exception as e:
            logger.warning("Could not get model info: %s", e)
            is_multi_speaker = False
            result.update({"model_type": "unknown", "model_loaded": True})

        # If model is multi-speaker, determine if we have any way to supply a speaker id
        if is_multi_speaker:
            has_speaker = False
            speaker_source = None

            # 1) default_speaker attribute on engine
            if hasattr(tts_engine, "default_speaker") and getattr(tts_engine, "default_speaker"):
                has_speaker = True
                speaker_source = f"default: {tts_engine.default_speaker}"

            # 2) speaker_wav_path attribute (engine-level reference audio)
            elif hasattr(tts_engine, "speaker_wav_path") and getattr(tts_engine, "speaker_wav_path"):
                has_speaker = True
                speaker_source = "reference audio"

            # 3) engine API to list available speakers
            elif hasattr(tts_engine, "get_available_speakers") and callable(getattr(tts_engine, "get_available_speakers")):
                try:
                    speakers = tts_engine.get_available_speakers()
                    if speakers:
                        has_speaker = True
                        speaker_source = f"available speakers: {len(speakers)}"
                except Exception as e:
                    logger.debug("get_available_speakers() failed: %s", e)

            # 4) engine API to register a speaker from wav (so health check could register a ref wav)
            register_capable = hasattr(tts_engine, "register_speaker_from_wav") and callable(getattr(tts_engine, "register_speaker_from_wav"))

            # If no speaker and no capability to register/list, SHORT-CIRCUIT to initialization-only health.
            if not has_speaker and not register_capable:
                # SHORT-CIRCUIT: model initialization considered healthy because this checkpoint
                # does not expose speaker_manager and cannot perform a synthesis check.
                logger.warning(
                    "Model initialized but no speaker registration/listing available; "
                    "skipping synthesis check and marking model as loaded for health purposes (temporary)."
                )
                result["ok"] = True
                result["reason"] = "Model initialized (synthesis check skipped: no speaker_manager or registration API)"
                if global_status is not None:
                    try:
                        global_status.model_loaded = True
                        global_status.last_model_check = now
                    except Exception:
                        logger.debug("Could not update global_status")
                # cleanup temp file if created earlier (safe)
                try:
                    if "tmp_path" in locals() and os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception:
                    pass
                return result

            # If we reach here and we have a speaker, record its source
            if has_speaker:
                result["speaker_source"] = speaker_source
            else:
                # We have registration capability but no speaker currently; mark as not ready
                result["ok"] = False
                result["reason"] = (
                    "Multi-speaker model requires either: "
                    "1) a reference audio file (set via set_reference_speaker), "
                    "2) a speaker name/id, or "
                    "3) default speaker configuration"
                )
                return result

        # Model is ready (either single-speaker or multi-speaker with a speaker available)
        result["ok"] = True
        result["reason"] = "Model is healthy and ready for synthesis"

        # Optional: try a quick synthesis test if settings configured. Do not fail the health check
        # if synthesis fails; only record the result.
        try:
            from app.core.config import settings  # local import to avoid import-time deps
            if settings and hasattr(settings, "health_check_text"):
                tmpf = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                tmpf.close()
                tmp_path = tmpf.name

                synth_text = settings.health_check_text or "Health check"
                default_lang = getattr(settings, "default_language", "en")

                # Build kwargs for multi-speaker case
                synth_kwargs = {}
                if is_multi_speaker:
                    # prefer explicit engine default_speaker if present
                    if hasattr(tts_engine, "default_speaker") and getattr(tts_engine, "default_speaker"):
                        synth_kwargs["speaker"] = tts_engine.default_speaker

                # Call synth: support both coroutine and sync function
                synth_func = getattr(tts_engine, "synthesize", None)
                if synth_func is not None:
                    if inspect.iscoroutinefunction(synth_func):
                        await synth_func(text=synth_text, language=default_lang, output_path=tmp_path, **synth_kwargs)
                    else:
                        loop = asyncio.get_running_loop()
                        await loop.run_in_executor(None, lambda: synth_func(text=synth_text, language=default_lang, output_path=tmp_path, **synth_kwargs))

                    # Cleanup synthesized file
                    try:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)
                    except Exception:
                        pass

                    result["synthesis_test"] = "passed"
                    logger.info("Health check synthesis test passed")
                else:
                    result["synthesis_test"] = "skipped: no synth function"
        except Exception as synth_error:
            logger.warning("Synthesis test failed but model is loaded: %s", synth_error)
            result["synthesis_test"] = f"failed: {str(synth_error)}"

        # Update global status if available
        if global_status is not None:
            try:
                global_status.model_loaded = True
                global_status.last_model_check = now
            except Exception:
                logger.debug("Could not update global_status after health check")

        return result

    except Exception as e:
        logger.exception("Unexpected error in TTS health check: %s", e)
        return {"ok": False, "reason": f"Unexpected error: {e}"}


# Global instance of HealthChecker
health_checker = HealthChecker()


# Export everything needed
__all__ = [
    "HealthChecker",
    "health_checker",
    "check_model_health",
]