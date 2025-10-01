# ================================
# FILE: app/api/voice_profile_routes.py  (UPDATED)
# ================================
import os
import tempfile
import logging
import asyncio
import shutil
import uuid
from pathlib import Path
from typing import Any, Optional, Dict

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Request, Form
from fastapi import Response, BackgroundTasks
from fastapi.responses import FileResponse, RedirectResponse
from starlette.status import HTTP_405_METHOD_NOT_ALLOWED

# Models & services (explicit imports preferred)
from app.models.voice_profiles import (
    VoiceRecordingSessionResponse,
    VoiceRecordingRequest,
    VoiceRecordingStepRequest,
    VoiceProfileListResponse,
    VoiceUsageRequest,
)
from app.services.voice_profile_service import VoiceProfileService
from app.services.audio_processor import AudioProcessor
from app.services.voice_cloning_service import VoiceCloningService
from app.api.dependencies import get_audio_processor, get_voice_cloning_service
from app.core.enhanced_exceptions import (
    ValidationException,
    SystemException,
    ErrorCode,
    EnhancedException,
)
from app.core.monitoring import system_monitor
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Optional FileManager provider (best-effort)
FileManager = None
get_file_manager = None
try:
    from app.services.file_manager import FileManager as _FM  # type: ignore
    FileManager = _FM
except Exception:
    FileManager = None

try:
    from app.api.dependencies import get_file_manager as _get_file_manager  # type: ignore
    get_file_manager = _get_file_manager
except Exception:
    get_file_manager = None


# -----------------------------
# Utility: call function once (sync or async) safely
# -----------------------------
async def _call_maybe_async(fn, *args, **kwargs):
    """
    Call fn with args/kwargs exactly once.

    - If fn is a coroutine function: await it.
    - Else run fn in thread pool via asyncio.to_thread to avoid blocking event loop.
    - If fn returns a coroutine object (rare), await it.
    """
    if asyncio.iscoroutinefunction(fn):
        return await fn(*args, **kwargs)

    # Sync function: run in thread to avoid blocking event loop
    result = await asyncio.to_thread(fn, *args, **kwargs)

    if asyncio.iscoroutine(result):
        return await result

    return result


# -----------------------------
# Adapter: adapt various service method names to expected route calls
# -----------------------------
class _VoiceProfileServiceAdapter:
    """
    Wrap underlying VoiceProfileService instance and provide an async-friendly surface
    with expected method names. If underlying implementation already matches expected
    names, we simply call them. Otherwise, we search for alternate candidate names.
    """

    def __init__(self, svc: Any):
        self._svc = svc
        self._candidates = {
            "start_recording_session": [
                "start_recording_session",
                "start_session",
                "create_session",
                "begin_recording_session",
                "create_recording_session",
            ],
            "submit_recording_step": [
                "submit_recording_step",
                "submit_step",
                "submit_recording",
                "add_recording_step",
                "save_step",
            ],
            "get_user_profiles": [
                "get_user_profiles",
                "list_user_profiles",
                "get_profiles",
                "list_profiles",
                "list_user_profiles_for",
            ],
            "use_voice_profile": [
                "use_voice_profile",
                "apply_voice_profile",
                "get_voice_profile_for_use",
                "use_profile",
                "synthesize_with_profile",
            ],
            "delete_voice_profile": [
                "delete_voice_profile",
                "delete_profile",
                "remove_profile",
                "delete_voice",
            ],
            # metadata retrieval candidates
            "get_profile_metadata": [
                "get_profile_metadata",
                "get_profile",
                "get_profile_info",
                "get_profile_details",
                "profile_metadata",
            ],
        }

    def _find_candidate(self, key: str):
        for name in self._candidates.get(key, []):
            if hasattr(self._svc, name):
                return getattr(self._svc, name)
        return None

    async def start_recording_session(self, *args, **kwargs):
        fn = self._find_candidate("start_recording_session")
        if fn is None:
            raise AttributeError("Underlying service does not implement a session-start method")
        return await _call_maybe_async(fn, *args, **kwargs)

    async def submit_recording_step(self, *args, **kwargs):
        fn = self._find_candidate("submit_recording_step")
        if fn is None:
            raise AttributeError("Underlying service does not implement a submit-recording method")
        return await _call_maybe_async(fn, *args, **kwargs)

    async def get_user_profiles(self, *args, **kwargs):
        fn = self._find_candidate("get_user_profiles")
        if fn is None:
            raise AttributeError("Underlying service does not implement a list-profiles method")
        return await _call_maybe_async(fn, *args, **kwargs)

    async def use_voice_profile(self, *args, **kwargs):
        fn = self._find_candidate("use_voice_profile")
        if fn is None:
            raise AttributeError("Underlying service does not implement use-profile method")
        return await _call_maybe_async(fn, *args, **kwargs)

    async def delete_voice_profile(self, *args, **kwargs):
        fn = self._find_candidate("delete_voice_profile")
        if fn is None:
            raise AttributeError("Underlying service does not implement delete-profile method")
        return await _call_maybe_async(fn, *args, **kwargs)

    async def get_profile_metadata(self, *args, **kwargs):
        """
        Try to fetch profile metadata (sample path, name, created_at, etc.) using
        one of several candidate method names on the underlying service.
        """
        fn = self._find_candidate("get_profile_metadata")
        if fn:
            return await _call_maybe_async(fn, *args, **kwargs)

        # fallback: if underlying service implements use_voice_profile and it's safe for metadata,
        # call it but expect it may return runtime payload; caller must handle.
        if hasattr(self._svc, "use_voice_profile"):
            return await _call_maybe_async(getattr(self._svc, "use_voice_profile"), *args, **kwargs)

        raise AttributeError("Underlying service cannot provide profile metadata")

    def __getattr__(self, item):
        # Forward other attributes to underlying service; raise AttributeError if not present.
        if hasattr(self._svc, item):
            return getattr(self._svc, item)
        raise AttributeError(f"{self.__class__.__name__} proxy: attribute {item!r} not found on wrapped service")


# -----------------------------
# Factory (singleton per-process)
# -----------------------------
# Simple module-level cache to avoid expensive repeated construction.
_VOICE_PROFILE_SERVICE_SINGLETON: Optional[Any] = None


def get_voice_profile_service(
    audio_processor: AudioProcessor = Depends(get_audio_processor),
    request: Request = None,
) -> Any:
    """
    Factory for VoiceProfileService - constructs once per process (lazy) and returns
    the same instance on subsequent calls. This factory *prefers* a service instance
    cached on app.state (created at startup in app/main.py). If not present, falls back
    to module-level singleton lazy construction.
    """
    global _VOICE_PROFILE_SERVICE_SINGLETON

    # If request provided and app.state has cached service (created at startup), prefer it.
    try:
        if request is not None:
            svc_from_state = getattr(request.app.state, "voice_profile_service", None)
            if svc_from_state:
                return svc_from_state
    except Exception:
        # fall back to module-level behavior
        pass

    if _VOICE_PROFILE_SERVICE_SINGLETON is not None:
        # also try to cache to app.state for future requests if request provided
        if request is not None and getattr(request.app.state, "voice_profile_service", None) is None:
            try:
                request.app.state.voice_profile_service = _VOICE_PROFILE_SERVICE_SINGLETON
            except Exception:
                pass
        return _VOICE_PROFILE_SERVICE_SINGLETON

    # Resolve storage directory from settings
    storage_dir = getattr(settings, "voice_profiles_dir", None) or getattr(settings, "VOICE_PROFILES_DIR", "voice_profiles")
    storage_dir = str(storage_dir)
    try:
        Path(storage_dir).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to prepare storage directory '{storage_dir}': {e}")

    # Try to get a file_manager instance if provider available
    file_manager_instance = None
    if get_file_manager is not None:
        try:
            file_manager_instance = get_file_manager()
        except Exception:
            file_manager_instance = None

    if file_manager_instance is None and FileManager is not None:
        try:
            file_manager_instance = FileManager()
        except Exception:
            file_manager_instance = None

    # Construct VoiceProfileService using introspection-friendly approach
    try:
        ctor = VoiceProfileService
        # Use kwargs mapping but be resilient to various constructor names
        kwargs: Dict[str, Any] = {}

        # Basic candidate names for ctor args
        possible_storage_names = ("storage_dir", "storage_path", "base_path", "root_path")
        possible_audio_names = ("audio_processor", "audio_proc", "audio")
        possible_file_manager_names = ("file_manager", "filemgr", "file_manager_instance")

        # Inspect constructor signature
        try:
            from inspect import signature
            sig = signature(ctor.__init__)
            params = list(sig.parameters.keys())[1:]  # drop self
        except Exception:
            params = []

        # Map storage
        for n in possible_storage_names:
            if n in params:
                kwargs[n] = storage_dir
                break

        # Map audio processor if supported
        for n in possible_audio_names:
            if n in params:
                kwargs[n] = audio_processor
                break

        # Map file manager if supported
        if file_manager_instance is not None:
            for n in possible_file_manager_names:
                if n in params:
                    kwargs[n] = file_manager_instance
                    break

        # Instantiate service
        if kwargs:
            service = ctor(**kwargs)
        else:
            # Fallback positional attempt (storage_dir, audio_processor, file_manager)
            service = ctor(storage_dir, audio_processor, file_manager_instance)

    except Exception as exc:
        logger.exception("Failed to construct VoiceProfileService: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to construct VoiceProfileService: {exc}")

    # Wrap with adapter if it does not provide expected async-friendly names
    expected_methods = [
        "start_recording_session",
        "submit_recording_step",
        "get_user_profiles",
        "use_voice_profile",
        "delete_voice_profile",
    ]
    missing = [m for m in expected_methods if not hasattr(service, m)]
    if not missing:
        _VOICE_PROFILE_SERVICE_SINGLETON = service
        # cache into app.state for future requests when possible
        try:
            if request is not None and getattr(request.app.state, "voice_profile_service", None) is None:
                request.app.state.voice_profile_service = service
        except Exception:
            pass
        return service

    logger.debug("Wrapping VoiceProfileService in adapter - missing methods: %s", missing)
    adapter = _VoiceProfileServiceAdapter(service)
    _VOICE_PROFILE_SERVICE_SINGLETON = adapter
    try:
        if request is not None and getattr(request.app.state, "voice_profile_service", None) is None:
            request.app.state.voice_profile_service = adapter
    except Exception:
        pass
    return adapter


# -----------------------------
# Simple current user extraction (demo-only)
# -----------------------------
def get_current_user_id(request: Request) -> str:
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        client_host = getattr(request.client, "host", None) or "unknown"
        user_id = f"user_{abs(hash(client_host)) % 10000}"
    return user_id


# -----------------------------
# Routes
# -----------------------------
@router.get("/profiles/start-recording")
async def start_recording_info():
    """
    Convenience helper for browsers / manual testing.
    Explains how to call the POST endpoint which actually starts sessions.
    """
    example_body = {
        "profile_name": "MyVoice",
        "description": "Optional description",
        "total_steps": 10,
    }
    return {
        "success": False,
        "message": "This endpoint expects a POST with a JSON body. Use POST /api/v1/profiles/start-recording",
        "example_request": example_body,
        "note": "POST returns a VoiceRecordingSessionResponse object on success.",
    }


@router.post("/profiles/start-recording", response_model=VoiceRecordingSessionResponse)
async def start_recording_session(
    request_data: VoiceRecordingRequest,
    request: Request,
    service: Any = Depends(get_voice_profile_service),
    user_id: str = Depends(get_current_user_id),
):
    """Start a new voice recording session"""
    request_id = getattr(request.state, "request_id", "unknown")

    try:
        logger.info(
            "Starting voice recording session",
            extra={"request_id": request_id, "user_id": user_id, "profile_name": request_data.profile_name},
        )

        result = await service.start_recording_session(user_id, request_data)

        logger.info(
            "Recording session started successfully",
            extra={"request_id": request_id, "profile_id": getattr(result, "profile_id", None)},
        )

        # Browser-friendly redirect when Accept: text/html
        accept = (request.headers.get("accept") or "").lower()
        if "text/html" in accept:
            return RedirectResponse(url="/voice-recorder", status_code=303)

        return result

    except EnhancedException:
        raise
    except Exception as e:
        logger.exception("Failed to start recording session", extra={"request_id": request_id})
        raise SystemException(
            message=f"Failed to start recording session: {str(e)}",
            error_code=ErrorCode.UNKNOWN_ERROR,
            user_message="Unable to start voice recording. Please try again.",
        )

@router.post("/profiles/submit-recording", response_model=VoiceRecordingSessionResponse)
async def submit_recording_step(
    request: Request,
    profile_id: str = Form(...),
    step_number: int = Form(...),
    audio_file: UploadFile = File(...),
    service: Any = Depends(get_voice_profile_service),
    user_id: str = Depends(get_current_user_id),
):
    """
    Submit a recording for a specific step.

    - Streams upload to a temp file to avoid loading entire file into memory.
    - Ensures temp file is removed afterwards.
    """
    request_id = getattr(request.state, "request_id", "unknown")

    temp_audio_path = None
    try:
        logger.info("Submitting recording step", extra={"request_id": request_id, "profile_id": profile_id, "step_number": step_number})

        # Validate extension quickly
        filename = getattr(audio_file, "filename", "") or ""
        suffix = Path(filename).suffix.lower()
        if suffix not in (".wav", ".mp3", ".flac", ".m4a"):
            raise ValidationException(
                message="Invalid audio file format",
                error_code=ErrorCode.AUDIO_FORMAT_ERROR,
                user_message="Please upload a valid audio file (WAV, MP3, FLAC, or M4A)",
            )

        # Create temp path (unique)
        temp_dir = getattr(settings, "temp_dir", None) or tempfile.gettempdir()
        Path(temp_dir).mkdir(parents=True, exist_ok=True)
        temp_audio_path = os.path.join(temp_dir, f"upload_{uuid.uuid4().hex}{suffix}")

        # Stream write via thread to avoid blocking event loop
        def _write_to_file(src_file, dest_path):
            # src_file is a SpooledTemporaryFile from Starlette/UploadFile
            with open(dest_path, "wb") as dest:
                src_file.seek(0)
                shutil.copyfileobj(src_file, dest)

        await asyncio.to_thread(_write_to_file, audio_file.file, temp_audio_path)

        # Build request object and call service
        request_obj = VoiceRecordingStepRequest(profile_id=profile_id, step_number=step_number, audio_data="")
        result = await service.submit_recording_step(user_id, request_obj, temp_audio_path)

        logger.info("Recording step submitted successfully", extra={"request_id": request_id, "profile_id": profile_id, "step_number": step_number})
        return result

    except EnhancedException:
        raise
    except Exception as e:
        logger.exception("Failed to submit recording", extra={"request_id": request_id})
        raise SystemException(
            message=f"Failed to process recording: {str(e)}",
            error_code=ErrorCode.AUDIO_PROCESSING_ERROR,
            user_message="Failed to process your recording. Please try again.",
        )
    finally:
        # Ensure temp file cleanup
        try:
            if temp_audio_path and os.path.exists(temp_audio_path):
                os.unlink(temp_audio_path)
        except Exception:
            logger.debug("Failed to remove temp audio file %s", temp_audio_path, exc_info=True)


@router.get("/profiles", response_model=VoiceProfileListResponse)
async def get_user_voice_profiles(
    request: Request,
    service: Any = Depends(get_voice_profile_service),
    user_id: str = Depends(get_current_user_id),
):
    """Get all voice profiles for the current user"""
    request_id = getattr(request.state, "request_id", "unknown")

    try:
        logger.info("Getting user voice profiles", extra={"request_id": request_id, "user_id": user_id})
        result = await service.get_user_profiles(user_id)
        logger.info("Retrieved voice profiles", extra={"request_id": request_id, "user_id": user_id, "total": getattr(result, 'total_count', None)})
        return result

    except EnhancedException:
        raise
    except Exception as e:
        logger.exception("Failed to get user profiles", extra={"request_id": request_id})
        raise SystemException(
            message=f"Failed to load profiles: {str(e)}",
            error_code=ErrorCode.UNKNOWN_ERROR,
            user_message="Unable to load your voice profiles. Please try again.",
        )


@router.post("/profiles/use-voice")
async def use_voice_profile_for_synthesis(
    request_data: VoiceUsageRequest,
    request: Request,
    voice_service: Any = Depends(get_voice_profile_service),
    tts_service: VoiceCloningService = Depends(get_voice_cloning_service),
    user_id: str = Depends(get_current_user_id),
):
    """Use a voice profile to synthesize speech"""
    request_id = getattr(request.state, "request_id", "unknown")

    try:
        logger.info(
            "Using voice profile for synthesis",
            extra={"request_id": request_id, "profile_id": request_data.profile_id, "text_length": len(request_data.text or "")},
        )

        # Get voice profile data (service should return dict-like or pydantic model)
        voice_data = await voice_service.use_voice_profile(user_id, request_data)

        # Defensive unpacking
        if isinstance(voice_data, dict):
            text = voice_data.get("text") or request_data.text
            language = voice_data.get("language", "en")
            speaker_wav_path = voice_data.get("voice_embedding_path") or voice_data.get("speaker_wav_path")
            speed = voice_data.get("speed", 1.0)
            profile_id = voice_data.get("profile_id")
            profile_name = voice_data.get("profile_name")
            quality = voice_data.get("quality", "unknown")
        else:
            # assume pydantic-like object
            text = getattr(voice_data, "text", request_data.text)
            language = getattr(voice_data, "language", "en")
            speaker_wav_path = getattr(voice_data, "voice_embedding_path", None) or getattr(voice_data, "speaker_wav_path", None)
            speed = getattr(voice_data, "speed", 1.0)
            profile_id = getattr(voice_data, "profile_id", None)
            profile_name = getattr(voice_data, "profile_name", None)
            quality = getattr(voice_data, "quality", "unknown")

        if not text:
            raise ValidationException(message="No text to synthesize", error_code=ErrorCode.INVALID_REQUEST, user_message="No text provided for synthesis")

        # Create TTSRequest (import local schema to avoid circular imports)
        from app.models.schemas import TTSRequest

        tts_request = TTSRequest(text=text, language=language, speaker_wav_path=speaker_wav_path, speed=speed)
        result = await tts_service.synthesize_speech(tts_request)

        if getattr(result, "success", False):
            logger.info("Voice synthesis completed successfully", extra={"request_id": request_id, "profile_id": profile_id})
            # convert to dict and augment
            try:
                result_dict = result.dict()
            except Exception:
                result_dict = dict(success=True, audio_file_path=getattr(result, "audio_file_path", None))

            result_dict["voice_profile"] = {"profile_id": profile_id, "profile_name": profile_name, "quality": quality}
            return result_dict
        else:
            return result

    except EnhancedException:
        raise
    except Exception as e:
        logger.exception("Failed to synthesize with voice profile", extra={"request_id": request_id})
        raise SystemException(
            message=f"Voice synthesis failed: {str(e)}",
            error_code=ErrorCode.UNKNOWN_ERROR,
            user_message="Unable to synthesize speech with your voice. Please try again.",
        )


@router.delete("/profiles/{profile_id}")
async def delete_voice_profile(
    profile_id: str,
    request: Request,
    service: Any = Depends(get_voice_profile_service),
    user_id: str = Depends(get_current_user_id),
):
    """Delete a voice profile"""
    request_id = getattr(request.state, "request_id", "unknown")

    try:
        logger.info("Deleting voice profile", extra={"request_id": request_id, "profile_id": profile_id})
        success = await service.delete_voice_profile(user_id, profile_id)

        if success:
            logger.info("Voice profile deleted successfully", extra={"request_id": request_id, "profile_id": profile_id})
            return {"success": True, "message": "Voice profile deleted successfully"}
        else:
            raise ValidationException(message="Profile not found or access denied", error_code=ErrorCode.FILE_NOT_FOUND, user_message="Voice profile not found")

    except EnhancedException:
        raise
    except Exception as e:
        logger.exception("Failed to delete voice profile", extra={"request_id": request_id})
        raise SystemException(
            message=f"Failed to delete profile: {str(e)}",
            error_code=ErrorCode.UNKNOWN_ERROR,
            user_message="Unable to delete voice profile. Please try again.",
        )


# -----------------------------
# Helper: ensure path is within base storage directory
# -----------------------------
def _is_within_base(path: Path, base: Path) -> bool:
    try:
        path_resolved = path.resolve()
        base_resolved = base.resolve()
        return base_resolved == path_resolved or base_resolved in path_resolved.parents
    except Exception:
        return False


@router.get("/profiles/{profile_id}/sample")
async def get_voice_sample(
    profile_id: str,
    request: Request,
    service: Any = Depends(get_voice_profile_service),
    user_id: str = Depends(get_current_user_id),
):
    """Get a sample audio from a voice profile"""
    request_id = getattr(request.state, "request_id", "unknown")

    try:
        logger.info("Fetching voice sample", extra={"request_id": request_id, "profile_id": profile_id})

        # Prefer dedicated metadata method if available
        try:
            profile_meta = await service.get_profile_metadata(user_id, profile_id)
        except AttributeError:
            # Adapter may raise if method is missing; fallback to use_voice_profile carefully
            # NOTE: this fallback may perform synthesis or other side-effects depending on impl.
            profile_meta = await service.use_voice_profile(user_id, VoiceUsageRequest(profile_id=profile_id, text="This is a sample of my voice profile."))

        # Normalize to dict-like
        if profile_meta is None:
            raise ValidationException(message="Voice profile not found", error_code=ErrorCode.FILE_NOT_FOUND, user_message="Voice sample not available")

        if isinstance(profile_meta, dict):
            sample_path = profile_meta.get("voice_embedding_path") or profile_meta.get("sample_path") or profile_meta.get("speaker_wav_path")
        else:
            sample_path = getattr(profile_meta, "voice_embedding_path", None) or getattr(profile_meta, "sample_path", None) or getattr(profile_meta, "speaker_wav_path", None)

        if not sample_path:
            raise ValidationException(message="Voice sample not found", error_code=ErrorCode.FILE_NOT_FOUND, user_message="Voice sample not available")

        sample_path = Path(sample_path)
        storage_base = Path(getattr(settings, "voice_profiles_dir", "voice_profiles")).resolve()
        if sample_path.exists() and _is_within_base(sample_path, storage_base):
            return FileResponse(path=str(sample_path), media_type="audio/wav", filename=f"voice_sample_{profile_id}.wav")
        else:
            raise ValidationException(message="Voice sample not found or access denied", error_code=ErrorCode.FILE_NOT_FOUND, user_message="Voice sample not available")

    except EnhancedException:
        raise
    except Exception as e:
        logger.exception("Failed to get voice sample", extra={"request_id": request_id})
        raise SystemException(
            message=f"Failed to get sample: {str(e)}",
            error_code=ErrorCode.UNKNOWN_ERROR,
            user_message="Unable to get voice sample. Please try again.",
        )
