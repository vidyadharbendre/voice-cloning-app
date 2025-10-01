# ================================
# FILE: app/services/voice_cloning_service.py
# ================================
import os
import uuid
import logging
import asyncio
from typing import Dict, Any, Optional, Callable, List

from app.interfaces.tts_interface import ITTSEngine
from app.interfaces.audio_processor_interface import IAudioProcessor
from app.interfaces.file_manager_interface import IFileManager
from app.models.schemas import TTSRequest, VoiceCloningRequest, TTSResponse, VoiceCloningResponse
from app.core.config import settings
from app.core.exceptions import VoiceCloningException, ValidationError, ModelLoadError, AudioProcessingError

logger = logging.getLogger("voice_cloning.service")


class VoiceCloningService:
    """Main service orchestrating voice cloning operations following Dependency Inversion Principle"""

    def __init__(self, tts_engine: ITTSEngine, audio_processor: IAudioProcessor, file_manager: IFileManager):
        self.tts_engine = tts_engine
        self.audio_processor = audio_processor
        self.file_manager = file_manager
        # Ensure output directory exists on construction (idempotent)
        try:
            os.makedirs(settings.output_dir, exist_ok=True)
        except Exception as e:
            # Log but do not raise here; failures will surface when writing files
            logger.exception("Unable to ensure output directory %s: %s", settings.output_dir, e)

    def _make_output_path(self, prefix: str, suffix: str = ".wav") -> str:
        # Safe filename with uuid
        filename = f"{prefix}_{uuid.uuid4().hex}{suffix}"
        return os.path.join(settings.output_dir, filename)

    def _abs_path(self, path: str) -> str:
        """Return absolute normalized path; safe when given None or empty."""
        if not path:
            return path
        return os.path.abspath(path)

    async def _try_register_speaker(self, reference_path: str, correlation_id: Optional[str] = None) -> Optional[str]:
        """
        Attempt to register a speaker in the underlying TTS engine so the model uses a stable speaker id
        rather than treating a temp filepath as the speaker key.

        Returns:
            speaker_id (str) if registration succeeded, otherwise None.

        Strategy:
        1. If the TTS engine exposes a first-class registration API (register_speaker_from_wav / create_speaker_from_wav),
           call it (await if coroutine).
        2. Otherwise, if the engine exposes _model and speaker_manager, attempt to call common helper names via
           asyncio.to_thread to avoid blocking the event loop.
        """

        if not reference_path or not os.path.exists(reference_path):
            return None

        # First: engine-level helper (preferred) - duck-typed
        register_fns = [
            "register_speaker_from_wav",  # hypothetical engine API
            "create_speaker_from_wav",
            "add_speaker_from_wav",
            "add_speaker",
        ]

        # 1) Try TTS engine method directly (supports sync or async)
        for fn_name in register_fns:
            fn = getattr(self.tts_engine, fn_name, None)
            if fn:
                try:
                    if asyncio.iscoroutinefunction(fn):
                        speaker_id = await fn(reference_path)
                    else:
                        # run sync registration in a thread if heavy
                        speaker_id = await asyncio.to_thread(fn, reference_path)
                    logger.info("Registered speaker via tts_engine.%s -> %s (correlation_id=%s)", fn_name, speaker_id, correlation_id)
                    return speaker_id
                except Exception as ex:
                    logger.warning("tts_engine.%s failed to register speaker: %s (correlation_id=%s)", fn_name, ex, correlation_id)

        # 2) Try to access underlying model's speaker manager if present
        tts_model = getattr(self.tts_engine, "_model", None)
        if tts_model is None:
            logger.debug("No underlying TTS model accessible for speaker registration (correlation_id=%s).", correlation_id)
            return None

        speaker_manager = getattr(tts_model, "speaker_manager", None) or getattr(getattr(tts_model, "synthesizer", None), "speaker_manager", None)
        if speaker_manager is None:
            logger.debug("No speaker_manager available on TTS model (correlation_id=%s).", correlation_id)
            return None

        # Inspect and try available helper method names on the speaker_manager
        manager_fn_names = [
            "create_speaker_from_wav",
            "add_speaker_from_wav",
            "add_speaker",
            "create_speaker",  # some variants
        ]

        def _call_manager(fn_name: str, ref_path: str) -> Optional[str]:
            try:
                fn = getattr(speaker_manager, fn_name, None)
                if not fn:
                    return None
                result = fn(ref_path)
                # Many APIs return speaker_id string; others may return tuple/dict - attempt to normalize
                if isinstance(result, str):
                    return result
                if isinstance(result, (list, tuple)) and result:
                    # some implementations may return (id, meta)
                    return str(result[0])
                # if method returns None but registers internally, attempt to find last added speaker id
                # Best-effort: check speaker_manager.speakers keys
                speakers_map = getattr(speaker_manager, "speakers", None)
                if isinstance(speakers_map, dict):
                    # heuristically return the most recent key if available
                    try:
                        return next(reversed(speakers_map.keys()))
                    except Exception:
                        return None
                return None
            except Exception as ex:
                logger.warning("speaker_manager.%s failed: %s", fn_name, ex)
                return None

        # run manager calls in a thread to avoid blocking
        for name in manager_fn_names:
            speaker_id = await asyncio.to_thread(_call_manager, name, reference_path)
            if speaker_id:
                logger.info("Registered speaker via speaker_manager.%s -> %s (correlation_id=%s)", name, speaker_id, correlation_id)
                return speaker_id

        logger.debug("Speaker registration attempts yielded no id (correlation_id=%s).", correlation_id)
        return None

    async def synthesize_speech(self, request: TTSRequest, correlation_id: Optional[str] = None) -> TTSResponse:
        """Synthesize speech from text.

        Optional correlation_id can be provided for tracing/logging.
        """
        log_ctx = {"correlation_id": correlation_id} if correlation_id else {}
        logger.info("synthesize_speech requested (text_len=%d, has_ref=%s) %s",
                    len(request.text or ""), bool(request.speaker_wav_path), log_ctx)

        # Validate request basics
        if not request.text or not request.text.strip():
            msg = "Text for synthesis is empty"
            logger.warning(msg + " %s", log_ctx)
            return TTSResponse(success=False, message=msg, error_code="VALIDATION_ERROR")

        try:
            output_path = self._make_output_path("tts")
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

            # Branch to clone_voice or simple tts
            if request.speaker_wav_path:
                # Ensure speaker file exists (defensive)
                ref_abs = self._abs_path(request.speaker_wav_path)
                if not os.path.exists(ref_abs):
                    msg = f"Provided speaker reference not found: {ref_abs}"
                    logger.warning(msg + " %s", log_ctx)
                    raise ValidationError(msg)

                # Try to pre-register speaker to avoid KeyError in model
                try:
                    speaker_id = await self._try_register_speaker(ref_abs, correlation_id=correlation_id)
                except Exception as ex:
                    logger.warning("Speaker registration attempt failed (non-fatal): %s (correlation_id=%s)", ex, correlation_id)
                    speaker_id = None

                # If speaker_id was created, prefer using it (some engines expect 'speaker' param)
                if speaker_id:
                    # Some engines accept a 'speaker' param via a synthesize call; try both clone_voice and synthesize if available
                    try:
                        # prefer engine-level clone method that accepts speaker id
                        if hasattr(self.tts_engine, "clone_voice_with_speaker_id"):
                            await self.tts_engine.clone_voice_with_speaker_id(
                                text=request.text,
                                speaker_id=speaker_id,
                                output_path=output_path,
                                language=request.language.value
                            )
                        else:
                            # fallback: let engine handle the reference path; engine should now find the registered speaker
                            await self.tts_engine.clone_voice(
                                text=request.text,
                                reference_audio_path=ref_abs,
                                output_path=output_path,
                                language=request.language.value
                            )
                    except KeyError as ke:
                        # Convert model-specific lookup errors into informative audio processing errors
                        logger.exception("TTS KeyError during synthesize_speech (speaker lookup): %s %s", ke, log_ctx)
                        raise AudioProcessingError(
                            f"TTS model failed to resolve speaker id '{ke}'. This may mean speaker registration didn't succeed."
                        )
                else:
                    # No speaker_id available; call engine with speaker_wav (engine should handle converting to speaker embedding)
                    try:
                        await self.tts_engine.clone_voice(
                            text=request.text,
                            reference_audio_path=ref_abs,
                            output_path=output_path,
                            language=request.language.value
                        )
                    except KeyError as ke:
                        logger.exception("TTS KeyError during synthesize_speech with speaker_wav: %s %s", ke, log_ctx)
                        raise AudioProcessingError(
                            "TTS model attempted to lookup an invalid speaker key (likely the wav path). "
                            "Pre-registration failed or model expects a different API. "
                            "Try registering speaker ids or use a different model/version."
                        )

            else:
                await self.tts_engine.synthesize(
                    text=request.text,
                    language=request.language.value,
                    output_path=output_path
                )

            logger.info("synthesize_speech succeeded: %s %s", output_path, log_ctx)
            return TTSResponse(success=True, audio_file_path=output_path, message="Speech synthesis completed successfully")

        except ValidationError as ve:
            logger.warning("synthesize_speech validation failed: %s %s", ve, log_ctx)
            return TTSResponse(success=False, message=str(ve), error_code="VALIDATION_ERROR")

        except ModelLoadError as mle:
            logger.error("synthesize_speech model load error: %s %s", mle, log_ctx, exc_info=True)
            return TTSResponse(success=False, message="Model not available: " + str(mle), error_code="MODEL_LOAD_ERROR")

        except AudioProcessingError as ape:
            logger.error("synthesize_speech audio processing error: %s %s", ape, log_ctx, exc_info=True)
            return TTSResponse(success=False, message=str(ape), error_code="AUDIO_PROCESSING_ERROR")

        except VoiceCloningException as vce:
            logger.exception("synthesize_speech voice cloning exception: %s %s", vce, log_ctx)
            return TTSResponse(success=False, message=str(vce), error_code="VOICE_CLONING_ERROR")

        except Exception as e:
            logger.exception("synthesize_speech unexpected error: %s %s", e, log_ctx)
            return TTSResponse(success=False, message="Internal error: " + str(e), error_code="INTERNAL_ERROR")

    async def clone_voice(self, request: VoiceCloningRequest, correlation_id: Optional[str] = None) -> VoiceCloningResponse:
        """Clone voice from reference audio."""
        log_ctx = {"correlation_id": correlation_id} if correlation_id else {}
        logger.info("clone_voice requested (ref_id=%s) %s", request.reference_audio_id, log_ctx)

        try:
            # Resolve the reference file path via file manager
            reference_path = await self.file_manager.get_file_path(request.reference_audio_id)
            if not reference_path:
                msg = f"Reference audio not found: {request.reference_audio_id}"
                logger.warning(msg + " %s", log_ctx)
                raise ValidationError(msg)

            reference_path = self._abs_path(reference_path)

            # Validate reference audio suitability
            valid = await self.audio_processor.validate_audio(reference_path)
            if not valid:
                msg = "Reference audio is not suitable for voice cloning"
                logger.warning(msg + " %s", log_ctx)
                raise ValidationError(msg)

            # Create output path
            output_path = self._make_output_path("cloned")
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

            # Try to pre-register speaker (best-effort)
            try:
                speaker_id = await self._try_register_speaker(reference_path, correlation_id=correlation_id)
            except Exception as ex:
                logger.warning("Speaker pre-registration failed (non-fatal): %s %s", ex, log_ctx)
                speaker_id = None

            # Perform voice cloning
            try:
                if speaker_id:
                    # Prefer engine method that accepts pre-registered speaker id if available
                    if hasattr(self.tts_engine, "clone_voice_with_speaker_id"):
                        await self.tts_engine.clone_voice_with_speaker_id(
                            text=request.text,
                            speaker_id=speaker_id,
                            output_path=output_path,
                            language=request.language.value
                        )
                    else:
                        # let engine locate the registered speaker by reference_path
                        await self.tts_engine.clone_voice(
                            text=request.text,
                            reference_audio_path=reference_path,
                            output_path=output_path,
                            language=request.language.value
                        )
                else:
                    # No pre-registered id; pass speaker_wav and let engine convert it
                    await self.tts_engine.clone_voice(
                        text=request.text,
                        reference_audio_path=reference_path,
                        output_path=output_path,
                        language=request.language.value
                    )
            except KeyError as ke:
                logger.exception("TTS KeyError during clone_voice (speaker lookup): %s %s", ke, log_ctx)
                raise AudioProcessingError(
                    f"TTS model failed to resolve speaker id/key '{ke}'. This commonly means the engine expected a registered speaker id but got a file path."
                )

            cloned_id = str(uuid.uuid4())
            logger.info("clone_voice succeeded (output=%s cloned_id=%s) %s", output_path, cloned_id, log_ctx)
            return VoiceCloningResponse(
                success=True,
                audio_file_path=output_path,
                cloned_voice_id=cloned_id,
                message="Voice cloning completed successfully"
            )

        except ValidationError as ve:
            logger.warning("clone_voice validation failed: %s %s", ve, log_ctx)
            return VoiceCloningResponse(success=False, message=str(ve), error_code="VALIDATION_ERROR")

        except ModelLoadError as mle:
            logger.error("clone_voice model load error: %s %s", mle, log_ctx, exc_info=True)
            return VoiceCloningResponse(success=False, message="Model not available: " + str(mle), error_code="MODEL_LOAD_ERROR")

        except AudioProcessingError as ape:
            logger.error("clone_voice audio processing error: %s %s", ape, log_ctx, exc_info=True)
            return VoiceCloningResponse(success=False, message=str(ape), error_code="AUDIO_PROCESSING_ERROR")

        except VoiceCloningException as vce:
            logger.exception("clone_voice voice cloning exception: %s %s", vce, log_ctx)
            return VoiceCloningResponse(success=False, message=str(vce), error_code="VOICE_CLONING_ERROR")

        except Exception as e:
            logger.exception("clone_voice unexpected error: %s %s", e, log_ctx)
            return VoiceCloningResponse(success=False, message="Internal error: " + str(e), error_code="INTERNAL_ERROR")
