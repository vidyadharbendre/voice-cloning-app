# ================================
# FILE: app/services/tts_engine.py
# ================================
import os
import re
import logging
import asyncio
import importlib
from typing import Dict, Any, Optional, Callable, List, Type
import inspect
from collections import OrderedDict
import time

import torch
from TTS.api import TTS

from app.interfaces.tts_interface import ITTSEngine
from app.core.config import settings
from app.core.exceptions import ModelLoadError, AudioProcessingError

logger = logging.getLogger(__name__)


def _get_safe_globals_ctx() -> Optional[Callable[[List[Type]], object]]:
    """
    Return a context-maker for allowlisting safe globals during torch.load.
    Prefer torch.serialization.safe_globals (context manager). If not available,
    try add_safe_globals and wrap it in a context-manager-like class.
    """
    try:
        from torch.serialization import safe_globals  # type: ignore

        def ctx(classes_list: List[Type]):
            return safe_globals(classes_list)

        return ctx
    except Exception:
        try:
            from torch.serialization import add_safe_globals  # type: ignore

            class _AddSafeGlobalsCtx:
                def __init__(self, classes_list: List[Type]):
                    self.classes = classes_list

                def __enter__(self):
                    add_safe_globals(self.classes)

                def __exit__(self, exc_type, exc, tb):
                    # add_safe_globals registers globally in older torch; nothing to rollback
                    return False

            def ctx(classes_list: List[Type]):
                return _AddSafeGlobalsCtx(classes_list)

            return ctx
        except Exception:
            return None


# Try to import common XTTS classes up-front (if available)
_safe_class_names = [
    "TTS.config.shared_configs.BaseDatasetConfig",
    "TTS.tts.configs.xtts_config.XttsConfig",
    "TTS.tts.models.xtts.XttsAudioConfig",
]
_initial_safe_classes: List[Type] = []

for fqcn in _safe_class_names:
    try:
        module_name, class_name = fqcn.rsplit(".", 1)
        mod = importlib.import_module(module_name)
        cls = getattr(mod, class_name)
        _initial_safe_classes.append(cls)
        logger.debug("Preloaded safe TTS class for allowlist: %s", fqcn)
    except Exception:
        logger.debug("Could not import prelisted safe class: %s (will try dynamic allowlist)", fqcn)


class XTTSTTSEngine(ITTSEngine):
    """XTTS-v2 TTS Engine with safe-loading and robust invocation of TTS API."""

    def __init__(self):
        self._model: Optional[TTS] = None
        self._initialized = False
        self.model_name = settings.default_model
        # prefer GPU only if settings allow and runtime has GPU
        self.use_gpu = bool(getattr(settings, "use_gpu", False) and torch.cuda.is_available())
        self._safe_ctx_factory = _get_safe_globals_ctx()
        # start with any initial safe classes we successfully imported
        self._safe_classes: List[Type] = list(_initial_safe_classes)

        # trust flag for fallback unpickle
        env_trust = os.getenv("TTS_TRUST_CHECKPOINTS", "").lower() in ("1", "true", "yes")
        self.trust_checkpoint = bool(getattr(settings, "tts_trust_checkpoints", False)) or env_trust

    # -----------------------------
    # Helper: robust invoker for tts_to_file
    # -----------------------------
    def _invoke_tts_to_file(self, text: str, output_path: str, language: Optional[str] = None,
                            speaker_wav: Optional[str] = None, speaker: Optional[str] = None, **kwargs):
        """
        Robust invoker for self._model.tts_to_file that:
         - tries multiple safe calling strategies,
         - auto-registers a speaker from speaker_wav when model requires `speaker`,
         - or selects a default registered speaker if available.
        Returns whatever tts_to_file returns. Raises AudioProcessingError on failure with aggregated info.
        """
        if self._model is None:
            raise AudioProcessingError("TTS model is not loaded")

        func = getattr(self._model, "tts_to_file", None)
        if func is None:
            raise AudioProcessingError("Underlying TTS object has no method tts_to_file")

        # Build canonical kwargs (do not pass both speaker_wav and speaker incorrectly)
        preferred_kwargs = OrderedDict([
            ("text", text),
            ("file_path", output_path),
            ("file", output_path),
            ("path", output_path),
            ("filename", output_path),
            ("language", language),
            ("speaker", speaker),
            ("speaker_wav", speaker_wav),
            ("speaker_wav_path", speaker_wav),
            ("speaker_id", speaker),
        ])

        def _compact(d):
            return {k: v for k, v in d.items() if v is not None}

        # Helper to attempt a specific call and capture exceptions
        def _try_call(call_kwargs):
            try:
                return func(**{**call_kwargs, **kwargs})
            except Exception as e:
                return e

        # Get signature if possible to prefer safe keywords
        try:
            sig = inspect.signature(func)
        except Exception:
            sig = None

        attempts = []
        last_exc = None

        # Strategy A: try keywords from signature (if available)
        if sig:
            kw_to_pass = {}
            for name in preferred_kwargs:
                if name in sig.parameters and preferred_kwargs[name] is not None:
                    kw_to_pass[name] = preferred_kwargs[name]
            if kw_to_pass:
                attempts.append(("keywords_from_signature", dict(kw_to_pass)))
                res = _try_call(kw_to_pass)
                if not isinstance(res, Exception):
                    return res
                last_exc = res
                logger.exception("tts_to_file try (keywords_from_signature) failed: %s", res)

                # If the model complained about missing speaker, handle below
        # Strategy B: try full preferred keywords (some APIs accept extra args)
        preferred = _compact(preferred_kwargs)
        attempts.append(("preferred_keywords", preferred))
        res = _try_call(preferred)
        if not isinstance(res, Exception):
            return res
        last_exc = res
        logger.exception("tts_to_file try (preferred_keywords) failed: %s", res)

        # If failure is specifically due to missing speaker for multi-speaker model,
        # attempt to register or select a speaker and retry.
        err_text = str(last_exc)
        if "Model is multi-speaker but no `speaker` is provided" in err_text or ("no `speaker` is provided" in err_text and "multi-speaker" in err_text):
            logger.info("Model requires speaker. Attempting to auto-resolve speaker from speaker_wav or existing speakers.")

            # 1) If speaker_wav provided => try to register it and use resulting speaker id
            resolved_speaker_id = None
            if speaker_wav:
                try:
                    # register_speaker_from_wav is async; we're in a thread so run it
                    resolved_speaker_id = asyncio.run(self.register_speaker_from_wav(speaker_wav))
                    logger.info("register_speaker_from_wav returned: %s", resolved_speaker_id)
                except Exception as reg_ex:
                    logger.warning("Failed to register speaker from wav (%s): %s", speaker_wav, reg_ex)

            # 2) If no id from registration, try to pick an existing speaker from speaker_manager
            if not resolved_speaker_id:
                try:
                    sm = getattr(self._model, "speaker_manager", None) or getattr(getattr(self._model, "synthesizer", None), "speaker_manager", None)
                    if sm is not None:
                        sp = getattr(sm, "speakers", None)
                        if isinstance(sp, dict) and sp:
                            # choose a deterministic default (first key)
                            resolved_speaker_id = next(iter(sp.keys()))
                            logger.info("Auto-selected existing speaker id: %s", resolved_speaker_id)
                except Exception as sm_ex:
                    logger.warning("Failed to inspect speaker_manager for default speaker: %s", sm_ex)

            # 3) If we resolved a speaker id, retry with explicit speaker=
            if resolved_speaker_id:
                retry_kwargs = dict(preferred)
                # ensure 'speaker' param used (and remove speaker_wav to avoid confusion)
                retry_kwargs["speaker"] = resolved_speaker_id
                retry_kwargs.pop("speaker_wav", None)
                retry_kwargs.pop("speaker_wav_path", None)
                # Keep only non-None
                retry_kwargs = _compact(retry_kwargs)
                attempts.append(("retry_with_resolved_speaker", retry_kwargs))
                res2 = _try_call(retry_kwargs)
                if not isinstance(res2, Exception):
                    return res2
                last_exc = res2
                logger.exception("tts_to_file retry_with_resolved_speaker failed: %s", res2)

            # 4) If no speaker resolved, raise a clear error
            raise AudioProcessingError(
                "Model requires a speaker but none could be resolved. "
                "Provide `speaker` (speaker id) or a valid `speaker_wav` to register."
            ) from last_exc

        # Next fallback strategies (positional) — keep them but be careful not to pass speaker_wav as speaker
        try:
            attempts.append(("positional_text_file_lang", None))
            res = func(text, output_path, language, **kwargs)
            return res
        except Exception as e:
            last_exc = e
            logger.exception("tts_to_file try (positional_text_file_lang) failed: %s", e)

        # Try positional but with speaker passed as keyword (for cloning workflows)
        try:
            attempts.append(("positional_text_file_plus_speaker_kw", {"speaker_wav": speaker_wav}))
            res = func(text, output_path, speaker_wav=speaker_wav, language=language, **kwargs)
            return res
        except Exception as e:
            last_exc = e
            logger.exception("tts_to_file try (positional_text_file_plus_speaker_kw) failed: %s", e)

        # All attempts failed -> raise aggregated error
        msg_lines = [
            "Failed to invoke tts_to_file using multiple strategies.",
            f"Attempts tried: {[a[0] for a in attempts]}",
            f"Last exception: {repr(last_exc)}"
        ]
        raise AudioProcessingError(" ; ".join(msg_lines)) from last_exc

    # -----------------------------
    # Safe globals and dynamic allowlist helpers
    # -----------------------------
    def _try_import_fqcn(self, fqcn: str) -> Optional[Type]:
        """
        Attempt to import a fully-qualified class name like 'pkg.mod.ClassName'.
        Return the class/type if successful, otherwise None.
        """
        try:
            module_name, class_name = fqcn.rsplit(".", 1)
            mod = importlib.import_module(module_name)
            cls = getattr(mod, class_name)
            logger.info("Dynamically imported allowlist class: %s", fqcn)
            return cls
        except Exception as ex:
            logger.warning("Failed to dynamically import allowlist class %s: %s", fqcn, ex)
            return None

    def _parse_unsupported_globals(self, err_msg: str) -> List[str]:
        """
        Parse torch's 'Unsupported global' error text and return list of FQCNs.
        It looks for lines like: 'Unsupported global: GLOBAL pkg.mod.ClassName'
        """
        matches = re.findall(r"GLOBAL\s+([A-Za-z0-9_.]+)", err_msg)
        unique = []
        for m in matches:
            if m not in unique:
                unique.append(m)
        return unique

    # -----------------------------
    # Initialization / loading
    # -----------------------------
    def _initialize_sync(self) -> None:
        """
        Synchronous initialization logic. It tries:
          1) safe-loading with safe_globals and a dynamic allowlist (preferred)
          2) fallback to forcing weights_only=False (trusted checkpoints only)
        The function will attempt to expand the safe allowlist by parsing the error messages
        and dynamically importing the missing classes up to a small retry limit.
        """
        def construct_tts():
            # TTS constructor may internally call torch.load; we rely on safe_globals context
            return TTS(self.model_name, gpu=self.use_gpu)

        # 1) Try safe load with dynamic allowlist
        if self._safe_ctx_factory is not None:
            logger.info(
                "Attempting safe load with PyTorch safe_globals (initial allowlist: %s)",
                [c.__module__ + "." + c.__name__ for c in self._safe_classes],
            )
            max_attempts = 6
            attempt = 0
            base_backoff = 1.0
            while attempt < max_attempts:
                attempt += 1
                try:
                    with self._safe_ctx_factory(self._safe_classes):
                        self._model = construct_tts()
                    logger.info("TTS model loaded using safe_globals allowlist on attempt %d", attempt)

                    # --------------------------
                    # Auto-register default speaker (if provided in settings)
                    # --------------------------
                    try:
                        sm = getattr(self._model, "speaker_manager", None) or getattr(getattr(self._model, "synthesizer", None), "speaker_manager", None)
                        if sm is not None:
                            sp = getattr(sm, "speakers", None)
                            if isinstance(sp, dict) and not sp:
                                default_wav = getattr(settings, "tts_default_speaker_wav", None)
                                if default_wav:
                                    try:
                                        # register_speaker_from_wav is async; this is sync init so use asyncio.run safely.
                                        # If asyncio.run cannot be used (running loop), we skip auto-registration and log.
                                        try:
                                            registered_id = asyncio.run(self.register_speaker_from_wav(default_wav))
                                            if registered_id:
                                                logger.info("Auto-registered default speaker from %s -> %s", default_wav, registered_id)
                                            else:
                                                logger.info("Default speaker WAV provided but registration returned None: %s", default_wav)
                                        except RuntimeError as re_err:
                                            # Cannot call asyncio.run from running event loop - skip and warn.
                                            logger.warning("Could not auto-register default speaker because an event loop is already running: %s", re_err)
                                        except Exception as reg_ex:
                                            logger.warning("Auto-registration of default speaker failed: %s", reg_ex)
                                    except Exception as nested_reg_ex:
                                        logger.warning("Auto-registration nested error: %s", nested_reg_ex)
                    except Exception:
                        # Non-fatal; continue initialization
                        logger.debug("Auto-register default speaker check failed (non-fatal)")

                    return
                except Exception as ex:
                    msg = str(ex)
                    logger.warning("Safe load attempt %d failed: %s", attempt, msg)
                    # Parse unsupported globals and try to import them and add to allowlist
                    new_fqcns = self._parse_unsupported_globals(msg)
                    if not new_fqcns:
                        logger.debug("No additional globals parsed from error message; breaking safe-load retry loop.")
                        break
                    added_any = False
                    for fqcn in new_fqcns:
                        cls = self._try_import_fqcn(fqcn)
                        if cls and cls not in self._safe_classes:
                            self._safe_classes.append(cls)
                            added_any = True
                            logger.info("Added %s to safe allowlist (now %d classes)", fqcn, len(self._safe_classes))
                    if not added_any:
                        logger.debug("No new allowlist classes could be imported; stopping safe load retries.")
                        break
                    # backoff before retrying
                    backoff = base_backoff * (2 ** (attempt - 1))
                    logger.info("Waiting %.2fs before retrying safe-load", backoff)
                    time.sleep(backoff)
                    # loop will retry with updated allowlist
            logger.warning("Safe-loading failed after %d attempts. Proceeding to fallback.", attempt)
        else:
            logger.warning("torch.serialization.safe_globals/add_safe_globals not available in this runtime; skipping safe-loading attempts.")

        # 2) Fallback: force torch.load weights_only=False (trusted checkpoint only)
        if not self.trust_checkpoint:
            logger.error(
                "Safe loading failed and trust_checkpoint is False. Will NOT attempt weights_only=False fallback. "
                "Set settings.tts_trust_checkpoints=True or environment TTS_TRUST_CHECKPOINTS=true to allow fallback "
                "only if you trust the checkpoint source."
            )
            raise ModelLoadError("TTS model requires non-weight unpickling but checkpoint trust is disabled.")

        logger.warning(
            "Attempting fallback load by temporarily forcing torch.load(weights_only=False). "
            "This performs full unpickling and must be used only for trusted checkpoints."
        )

        orig_torch_load = torch.load

        def _torch_load_force_no_weights_only(*args, **kwargs):
            kwargs.setdefault("weights_only", False)
            return orig_torch_load(*args, **kwargs)

        try:
            torch.load = _torch_load_force_no_weights_only
            self._model = construct_tts()
            logger.info("TTS model loaded using fallback (weights_only=False).")

            # After fallback load also try auto-register default speaker (same logic as above)
            try:
                sm = getattr(self._model, "speaker_manager", None) or getattr(getattr(self._model, "synthesizer", None), "speaker_manager", None)
                if sm is not None:
                    sp = getattr(sm, "speakers", None)
                    if isinstance(sp, dict) and not sp:
                        default_wav = getattr(settings, "tts_default_speaker_wav", None)
                        if default_wav:
                            try:
                                try:
                                    registered_id = asyncio.run(self.register_speaker_from_wav(default_wav))
                                    if registered_id:
                                        logger.info("Auto-registered default speaker from %s -> %s", default_wav, registered_id)
                                    else:
                                        logger.info("Default speaker WAV provided but registration returned None: %s", default_wav)
                                except RuntimeError as re_err:
                                    logger.warning("Could not auto-register default speaker because an event loop is already running: %s", re_err)
                                except Exception as reg_ex:
                                    logger.warning("Auto-registration of default speaker failed: %s", reg_ex)
                            except Exception as nested_reg_ex:
                                logger.warning("Auto-registration nested error: %s", nested_reg_ex)
            except Exception:
                logger.debug("Auto-register default speaker check failed after fallback (non-fatal)")

            return
        except Exception as ex:
            logger.exception("Fallback (weights_only=False) also failed: %s", ex)
            raise
        finally:
            # restore original function to avoid side effects
            torch.load = orig_torch_load

    async def initialize(self) -> None:
        """Initialize the TTS engine (non-blocking)."""
        if self._initialized:
            return

        try:
            await asyncio.to_thread(self._initialize_sync)
            self._initialized = True
            logger.info("TTS engine initialized (model=%s, gpu=%s)", self.model_name, self.use_gpu)
        except Exception as e:
            logger.exception("TTS initialization failed")
            raise ModelLoadError(f"Failed to initialize TTS model: {e}") from e

    # -----------------------------
    # Speaker registration helper
    # -----------------------------
    async def register_speaker_from_wav(self, wav_path: str) -> Optional[str]:
        """
        Try to register a speaker from a wav and return a speaker_id if successful.
        Tries engine-level registration helpers, or falls back to underlying model.speaker_manager helpers.
        Returns None if registration failed / helper not present.
        """
        if not wav_path or not os.path.exists(wav_path):
            logger.debug("register_speaker_from_wav: wav_path missing or not found: %s", wav_path)
            return None

        # Ensure model is initialized (so speaker_manager exists)
        if not self._initialized:
            await self.initialize()

        # Common function names to try on the engine itself
        engine_fn_names = [
            "register_speaker_from_wav",
            "create_speaker_from_wav",
            "add_speaker_from_wav",
            "add_speaker",
        ]

        for name in engine_fn_names:
            fn = getattr(self, name, None)
            if fn:
                try:
                    if asyncio.iscoroutinefunction(fn):
                        speaker_id = await fn(wav_path)
                    else:
                        speaker_id = await asyncio.to_thread(fn, wav_path)
                    logger.info("Registered speaker via engine.%s -> %s", name, speaker_id)
                    return speaker_id
                except Exception as ex:
                    logger.warning("Engine-level registration %s failed: %s", name, ex)

        # Try underlying TTS model speaker_manager
        tts_model = getattr(self, "_model", None)
        if tts_model is None:
            logger.debug("No _model available for speaker registration")
            return None

        speaker_manager = getattr(tts_model, "speaker_manager", None) or getattr(getattr(tts_model, "synthesizer", None), "speaker_manager", None)
        if speaker_manager is None:
            logger.debug("No speaker_manager found on TTS model")
            return None

        manager_fn_names = ["create_speaker_from_wav", "add_speaker_from_wav", "add_speaker", "create_speaker"]

        def _call_manager(fn_name: str, path: str) -> Optional[str]:
            try:
                fn = getattr(speaker_manager, fn_name, None)
                if not fn:
                    return None
                res = fn(path)
                if isinstance(res, str):
                    return res
                if isinstance(res, (tuple, list)) and res:
                    return str(res[0])
                sp = getattr(speaker_manager, "speakers", None)
                if isinstance(sp, dict) and sp:
                    try:
                        return next(reversed(sp.keys()))
                    except Exception:
                        return None
                return None
            except Exception as exc:
                logger.warning("speaker_manager.%s failed: %s", fn_name, exc)
                return None

        for name in manager_fn_names:
            speaker_id = await asyncio.to_thread(_call_manager, name, wav_path)
            if speaker_id:
                logger.info("Registered speaker via speaker_manager.%s -> %s", name, speaker_id)
                return speaker_id

        logger.debug("register_speaker_from_wav: no registration method succeeded")
        return None

    # -----------------------------
    # Synthesis / cloning methods
    # -----------------------------

    async def synthesize(self, text: str, language: str, output_path: str, speaker: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Synthesize text to speech without voice cloning"""
        if not self._initialized:
            await self.initialize()

        if self._model is None:
            raise AudioProcessingError("TTS model is not loaded")

        try:
            out_dir = os.path.dirname(output_path) or "."
            os.makedirs(out_dir, exist_ok=True)

            # If model is multi-speaker and no speaker provided, try to pick a default speaker id
            try:
                speakers = getattr(self._model, "speaker_manager", None)
                speaker_keys = None
                if speakers:
                    sp_dict = getattr(speakers, "speakers", None)
                    if isinstance(sp_dict, dict) and sp_dict:
                        speaker_keys = list(sp_dict.keys())
            except Exception:
                speaker_keys = None

            # 1) Accept explicit speaker passed by caller
            chosen_speaker = speaker

            # 2) If no explicit speaker, prefer configured default speaker id
            if chosen_speaker is None:
                cfg_default_speaker = getattr(settings, "tts_default_speaker_id", None)
                if cfg_default_speaker is not None:
                    chosen_speaker = cfg_default_speaker
                    logger.info("Using configured default speaker id from settings: %s", chosen_speaker)

            # 3) If still none, pick first registered speaker if available
            if chosen_speaker is None and speaker_keys:
                chosen_speaker = speaker_keys[0]
                logger.info("No speaker provided; using first registered speaker id: %s", chosen_speaker)

            # 4) If still none, decide policy:
            #    - If admin enabled fallback (settings.tts_allow_fallback_without_speaker=True), attempt tts anyway.
            #    - Otherwise raise a clear AudioProcessingError as before.
            if chosen_speaker is None and not speaker_keys:
                allow_fallback = bool(getattr(settings, "tts_allow_fallback_without_speaker", False))
                if allow_fallback:
                    logger.warning(
                        "No speaker provided and no registered speakers found. "
                        "Attempting synthesis without a speaker due to tts_allow_fallback_without_speaker=True. "
                        "This may fail if the model strictly requires a speaker."
                    )
                    # Attempt invocation and if it fails, return a structured failure
                    def _attempt_no_speaker():
                        return self._invoke_tts_to_file(text=text, output_path=output_path, language=language, speaker=None, **kwargs)
                    try:
                        await asyncio.to_thread(_attempt_no_speaker)
                        return {
                            "success": True,
                            "output_path": output_path,
                            "speaker": None,
                            "message": "TTS synthesis completed (no speaker was provided)"
                        }
                    except Exception as ex:
                        logger.exception("Synthesis without speaker failed: %s", ex)
                        raise AudioProcessingError(
                            "Model is multi-speaker and requires a speaker; synthesis without a speaker failed. "
                            "Provide `speaker` id or set up a registered speaker."
                        ) from ex
                else:
                    # strict behavior (original)
                    raise AudioProcessingError(
                        "Model is multi-speaker and no speaker was provided. "
                        "Please pass a `speaker` id for synthesis or register one via the speaker_manager."
                    )

            def _sync_call():
                return self._invoke_tts_to_file(text=text, output_path=output_path, language=language, speaker=chosen_speaker, **kwargs)

            await asyncio.to_thread(_sync_call)

            return {
                "success": True,
                "output_path": output_path,
                "speaker": chosen_speaker,
                "message": "TTS synthesis completed successfully"
            }
        except AudioProcessingError:
            # re-raise to preserve message and status
            raise
        except Exception as e:
            logger.exception("TTS synthesis error: %s", e)
            raise AudioProcessingError(f"TTS synthesis failed: {e}") from e

    async def clone_voice(self, text: str, reference_audio_path: str, output_path: str, language: str, **kwargs) -> Dict[str, Any]:
        """Clone voice from reference audio"""
        if not self._initialized:
            await self.initialize()

        if self._model is None:
            raise AudioProcessingError("TTS model is not loaded")

        try:
            if not os.path.exists(reference_audio_path):
                raise AudioProcessingError(f"Reference audio file not found: {reference_audio_path}")

            out_dir = os.path.dirname(output_path) or "."
            os.makedirs(out_dir, exist_ok=True)

            # Register the reference WAV as a speaker (returns speaker id) if possible
            speaker_id = await self.register_speaker_from_wav(reference_audio_path)
            if not speaker_id:
                # If we could not register, raise a clear error (avoids KeyError)
                raise AudioProcessingError(
                    "Failed to register reference audio as a speaker. Ensure the WAV is compatible and the TTS package supports registration."
                )

            # Use speaker id (not raw wav path) for multi-speaker models
            def _sync_call():
                return self._invoke_tts_to_file(
                    text=text,
                    output_path=output_path,
                    language=language,
                    speaker=speaker_id,
                    **kwargs
                )

            await asyncio.to_thread(_sync_call)

            return {
                "success": True,
                "output_path": output_path,
                "reference_audio": reference_audio_path,
                "speaker_id": speaker_id,
                "message": "Voice cloning completed successfully"
            }
        except KeyError as ke:
            logger.exception("Voice cloning KeyError: speaker lookup failed: %s", ke)
            raise AudioProcessingError(f"Voice cloning failed (speaker lookup): {ke}") from ke
        except AudioProcessingError:
            raise
        except Exception as e:
            logger.exception("Voice cloning error: %s", e)
            raise AudioProcessingError(f"Voice cloning failed: {e}") from e


    # -----------------------------
    # Utility
    # -----------------------------
    def is_initialized(self) -> bool:
        """Check if engine is initialized"""
        return self._initialized
