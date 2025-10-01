# ================================
# FILE: app/services/voice_profile_service.py
# ================================
"""
VoiceProfileService - resilient to missing Pydantic response classes.

This implementation:
 - avoids hard-failing imports from `app.models.voice_profiles`
 - uses pydantic models when available, otherwise returns lightweight
   objects that support attribute access + dict() for serialization.
"""
from __future__ import annotations

import os
import uuid
import json
import shutil
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

from app.core.config import settings
from app.services.audio_processor import AudioProcessor
from app.core.enhanced_exceptions import ValidationException, SystemException, ErrorCode

# optional FileManager import (best-effort)
try:
    from app.services.file_manager import FileManager  # type: ignore
except Exception:
    FileManager = None

# Try to import pydantic response models — but do not crash if they are missing.
_VRS = None
_VPLR = None
_VPS = None
try:
    from app.models.voice_profiles import (
        VoiceRecordingSessionResponse,
        VoiceProfileListResponse,
        VoiceProfileSummary,
    )
    _VRS = VoiceRecordingSessionResponse
    _VPLR = VoiceProfileListResponse
    _VPS = VoiceProfileSummary
except Exception:
    # missing/changed model names; we'll fall back to lightweight responses
    _VRS = None
    _VPLR = None
    _VPS = None

logger = logging.getLogger(__name__)

# Replace / extend these prompts with your real dataset
PROMPTS = [
    "Please say: The quick brown fox jumps over the lazy dog.",
    "Please say: How razorback-jumping frogs can level six piqued gymnasts.",
    "Please say: She sells seashells by the seashore.",
    "Please say: Today is a nice day for a walk in the park."
]


class ResponseObj:
    """
    Lightweight response object that:
     - exposes attributes (e.g. obj.profile_id)
     - provides dict() for FastAPI serialization
    """
    def __init__(self, data: Dict[str, Any]):
        self.__dict__.update(data)

    def dict(self) -> Dict[str, Any]:
        # return a plain serializable dict
        return {k: v for k, v in self.__dict__.items()}


class VoiceProfileService:
    """
    Manage voice profile recording sessions and profiles.

    Constructor signature tries to be backward-compatible: storage_dir may be
    passed as positional/keyword or derived from settings.
    """

    def __init__(
        self,
        audio_processor: Optional[AudioProcessor] = None,
        file_manager: Optional[object] = None,
        storage_dir: Optional[str] = None,
    ):
        self.audio_processor = audio_processor or AudioProcessor()
        self.file_manager = file_manager or (FileManager() if FileManager else None)

        storage_dir = storage_dir or getattr(settings, "voice_profiles_dir", None) or getattr(
            settings, "VOICE_PROFILES_DIR", "voice_profiles"
        )
        self.storage_dir = Path(str(storage_dir))
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.exception("Failed to prepare storage directory %s: %s", self.storage_dir, e)
            raise SystemException(message=f"Unable to prepare storage dir: {e}", error_code=ErrorCode.STORAGE_FULL)

    # ---- internal helpers ----
    def _profile_dir(self, profile_id: str) -> Path:
        return self.storage_dir / profile_id

    def _meta_path(self, profile_id: str) -> Path:
        return self._profile_dir(profile_id) / "meta.json"

    def _load_meta(self, profile_id: str) -> Dict[str, Any]:
        p = self._meta_path(profile_id)
        if not p.exists():
            raise ValidationException(message=f"Profile metadata not found: {profile_id}", error_code=ErrorCode.FILE_NOT_FOUND)
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            logger.exception("Failed to read meta for %s: %s", profile_id, e)
            raise SystemException(message="Failed to read profile metadata", error_code=ErrorCode.FILE_CORRUPTION)

    def _save_meta(self, profile_id: str, meta: Dict[str, Any]) -> None:
        p = self._meta_path(profile_id)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.exception("Failed to write meta for %s: %s", profile_id, e)
            raise SystemException(message="Failed to save profile metadata", error_code=ErrorCode.FILE_UPLOAD_ERROR)

    # ---- public methods used by routes ----
    async def start_recording_session(self, user_id: str, request: Any) -> Any:
        """
        Create a new voice profile recording session and return session details.
        The `request` is expected to have .profile_name and optionally .total_steps.
        """
        try:
            profile_name = getattr(request, "profile_name", None) or ""
            profile_name = str(profile_name).strip()
            if not profile_name:
                raise ValidationException(message="Profile name required", error_code=ErrorCode.MISSING_PARAMETER)

            total_steps = int(getattr(request, "total_steps", 3) or 3)
            if total_steps <= 0:
                total_steps = 3

            profile_id = uuid.uuid4().hex
            created_at = time.time()

            prompts = PROMPTS[:total_steps] if len(PROMPTS) >= total_steps else (PROMPTS * ((total_steps // max(1, len(PROMPTS))) + 1))[:total_steps]

            meta = {
                "profile_id": profile_id,
                "profile_name": profile_name,
                "owner": user_id,
                "created_at": created_at,
                "updated_at": created_at,
                "total_steps": total_steps,
                "current_step": 1,
                "status": "recording",
                "prompts": prompts,
                "quality": "processing",
                "times_used": 0,
            }

            self._save_meta(profile_id, meta)

            response_payload = {
                "success": True,
                "profile_id": profile_id,
                "profile_name": profile_name,
                "total_steps": meta["total_steps"],
                "current_step": meta["current_step"],
                "progress_percentage": 0.0,
                "next_prompt": meta["prompts"][0] if meta["prompts"] else None,
                "message": "Recording session started",
            }

            # return pydantic object if available, else ResponseObj
            if _VRS:
                try:
                    return _VRS(**response_payload)
                except Exception:
                    return ResponseObj(response_payload)
            else:
                return ResponseObj(response_payload)

        except ValidationException:
            raise
        except Exception as e:
            logger.exception("start_recording_session failed: %s", e)
            raise SystemException(message=f"Failed to start recording session: {e}", error_code=ErrorCode.UNKNOWN_ERROR)

    async def submit_recording_step(self, user_id: str, request: Any, temp_audio_path: str) -> Any:
        """
        Accept uploaded audio for a step, validate and store it, update progress.
        `request` should expose .profile_id and .step_number
        """
        try:
            profile_id = getattr(request, "profile_id", None)
            step_number = int(getattr(request, "step_number", 0))

            if not profile_id:
                raise ValidationException(message="profile_id required", error_code=ErrorCode.MISSING_PARAMETER)

            meta = self._load_meta(profile_id)
            if meta.get("owner") != user_id:
                raise ValidationException(message="Access denied to this profile", error_code=ErrorCode.FILE_NOT_FOUND)

            if step_number != meta.get("current_step"):
                raise ValidationException(message="Unexpected step number", error_code=ErrorCode.INVALID_INPUT)

            if not os.path.exists(temp_audio_path):
                raise ValidationException(message="Uploaded audio file missing", error_code=ErrorCode.FILE_NOT_FOUND)

            # validate audio content
            valid = await self.audio_processor.validate_audio(temp_audio_path)
            if not valid:
                raise ValidationException(message="Reference audio is not suitable for voice cloning", error_code=ErrorCode.AUDIO_QUALITY_POOR)

            # move file into profile dir
            profdir = self._profile_dir(profile_id)
            profdir.mkdir(parents=True, exist_ok=True)
            dest = profdir / f"step_{step_number}.wav"
            try:
                shutil.move(temp_audio_path, str(dest))
            except Exception:
                shutil.copy2(temp_audio_path, dest)
                try:
                    os.remove(temp_audio_path)
                except Exception:
                    pass

            # update meta and status
            meta["current_step"] = meta.get("current_step", 1) + 1
            meta["updated_at"] = time.time()
            if meta["current_step"] > meta.get("total_steps", 1):
                meta["status"] = "ready"
                meta["current_step"] = meta.get("total_steps", 1)
                meta["quality"] = "ready"
            self._save_meta(profile_id, meta)

            progress = (meta["current_step"] - 1) / meta["total_steps"] * 100.0
            next_prompt = None
            if meta.get("status") != "ready" and meta.get("current_step") <= meta.get("total_steps"):
                prompts = meta.get("prompts", [])
                idx = meta["current_step"] - 1
                if 0 <= idx < len(prompts):
                    next_prompt = prompts[idx]

            response_payload = {
                "success": True,
                "profile_id": profile_id,
                "profile_name": meta.get("profile_name"),
                "total_steps": meta.get("total_steps"),
                "current_step": meta.get("current_step"),
                "progress_percentage": progress,
                "next_prompt": next_prompt,
                "message": "Step submitted successfully",
            }

            if _VRS:
                try:
                    return _VRS(**response_payload)
                except Exception:
                    return ResponseObj(response_payload)
            else:
                return ResponseObj(response_payload)

        except ValidationException:
            raise
        except Exception as e:
            logger.exception("submit_recording_step failed: %s", e)
            raise SystemException(message=f"Failed to submit recording: {e}", error_code=ErrorCode.UNKNOWN_ERROR)

    async def get_user_profiles(self, user_id: str) -> Any:
        """
        Return a listing of voice profiles for a user (summary).
        """
        try:
            profiles: List[Dict[str, Any]] = []
            for p in self.storage_dir.iterdir():
                if not p.is_dir():
                    continue
                try:
                    meta_path = p / "meta.json"
                    if not meta_path.exists():
                        continue
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    if meta.get("owner") != user_id:
                        continue

                    item = {
                        "profile_id": meta.get("profile_id"),
                        "profile_name": meta.get("profile_name"),
                        "created_at": meta.get("created_at"),
                        "status": meta.get("status", "unknown"),
                        "quality": meta.get("quality", "processing"),
                        "times_used": meta.get("times_used", 0),
                    }
                    if _VPS:
                        try:
                            profiles.append(_VPS(**item))
                        except Exception:
                            profiles.append(item)
                    else:
                        profiles.append(item)
                except Exception:
                    logger.exception("Failed to read profile meta for %s", p)

            resp_payload = {"total_count": len(profiles), "profiles": profiles}
            if _VPLR:
                try:
                    return _VPLR(**resp_payload)
                except Exception:
                    return ResponseObj(resp_payload)
            else:
                return ResponseObj(resp_payload)

        except Exception as e:
            logger.exception("get_user_profiles failed: %s", e)
            raise SystemException(message="Failed to list profiles", error_code=ErrorCode.UNKNOWN_ERROR)

    async def use_voice_profile(self, user_id: str, request: Any) -> Dict[str, Any]:
        """
        Prepare data required to synthesize from stored profile.
        Returns plain dict (routes expect keys like 'voice_embedding_path', 'text', 'language').
        """
        try:
            profile_id = getattr(request, "profile_id", None)
            if not profile_id:
                raise ValidationException(message="profile_id required", error_code=ErrorCode.MISSING_PARAMETER)

            meta = self._load_meta(profile_id)
            if meta.get("owner") != user_id:
                raise ValidationException(message="Access denied", error_code=ErrorCode.FILE_NOT_FOUND)
            if meta.get("status") != "ready":
                raise ValidationException(message="Profile not ready for use", error_code=ErrorCode.INVALID_INPUT)

            profdir = self._profile_dir(profile_id)
            candidate = None
            for fname in ("speaker.wav", "step_1.wav", "step_2.wav"):
                p = profdir / fname
                if p.exists():
                    candidate = str(p)
                    break
            if not candidate:
                wavs = list(profdir.glob("*.wav"))
                if wavs:
                    candidate = str(wavs[0])
            if not candidate:
                raise SystemException(message="No reference audio file found for profile", error_code=ErrorCode.FILE_NOT_FOUND)

            meta["times_used"] = int(meta.get("times_used", 0)) + 1
            meta["updated_at"] = time.time()
            self._save_meta(profile_id, meta)

            return {
                "text": getattr(request, "text", settings.health_check_text or "Hello"),
                "language": getattr(request, "language", "en"),
                "voice_embedding_path": candidate,
                "speed": float(getattr(request, "speed", 1.0)),
                "profile_id": profile_id,
                "profile_name": meta.get("profile_name"),
                "quality": meta.get("quality", "ready"),
            }

        except ValidationException:
            raise
        except Exception as e:
            logger.exception("use_voice_profile failed: %s", e)
            raise SystemException(message=f"Failed to use voice profile: {e}", error_code=ErrorCode.UNKNOWN_ERROR)

    async def delete_voice_profile(self, user_id: str, profile_id: str) -> bool:
        """
        Delete a profile directory if owned by user.
        """
        try:
            meta = self._load_meta(profile_id)
            if meta.get("owner") != user_id:
                raise ValidationException(message="Access denied", error_code=ErrorCode.FILE_NOT_FOUND)

            profdir = self._profile_dir(profile_id)
            if profdir.exists():
                shutil.rmtree(profdir)
            return True

        except ValidationException:
            raise
        except Exception as e:
            logger.exception("delete_voice_profile failed: %s", e)
            raise SystemException(message=f"Failed to delete profile: {e}", error_code=ErrorCode.UNKNOWN_ERROR)
