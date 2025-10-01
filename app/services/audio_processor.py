# ================================
# FILE: app/services/audio_processor.py
# ================================
"""
Concrete AudioProcessor implementation.

- Reads sample-rate/hop/win settings defensively (backwards-compatible).
- Validates and loads audio using librosa (preferred) and soundfile.
- Provides simple preprocessing utilities.
"""

import os
import logging
from typing import Tuple, Optional

try:  # pragma: no cover - optional dependency handling
    import librosa  # type: ignore
except Exception:  # pragma: no cover - noqa: BLE001 (broad to handle optional dep absence)
    librosa = None  # type: ignore

try:  # pragma: no cover - optional dependency handling
    import soundfile as sf  # type: ignore
except Exception:  # pragma: no cover - noqa: BLE001
    sf = None  # type: ignore

import numpy as np

from app.interfaces.audio_processor_interface import IAudioProcessor
from app.core.config import settings
from app.core.exceptions import AudioProcessingError

logger = logging.getLogger(__name__)


class AudioProcessor(IAudioProcessor):
    """Concrete implementation of audio processing following Single Responsibility Principle"""

    def __init__(self) -> None:
        # sample rate (backwards-compatible)
        try:
            self.target_sr = int(
                getattr(settings, "sample_rate", None)
                or getattr(settings, "default_sample_rate", None)
                or getattr(settings, "DEFAULT_SAMPLE_RATE", 22050)
            )
        except Exception:
            self.target_sr = 22050

        # hop / win length (backwards-compatible)
        try:
            self.hop_length = int(getattr(settings, "hop_length", None) or getattr(settings, "HOP_LENGTH", 256))
        except Exception:
            self.hop_length = 256

        try:
            self.win_length = int(getattr(settings, "win_length", None) or getattr(settings, "WIN_LENGTH", 1024))
        except Exception:
            self.win_length = 1024

        # size/duration constraints
        try:
            self.max_size_bytes = int(getattr(settings, "max_upload_size", 50 * 1024 * 1024))
        except Exception:
            self.max_size_bytes = 50 * 1024 * 1024

        self.min_duration = float(getattr(settings, "min_audio_duration", getattr(settings, "MIN_AUDIO_DURATION", 0.5)))
        self.max_duration = float(getattr(settings, "max_audio_duration", getattr(settings, "MAX_AUDIO_DURATION", 300.0)))

        logger.info(
            "AudioProcessor init sr=%s hop_length=%s win_length=%s max_size=%d",
            self.target_sr,
            self.hop_length,
            self.win_length,
            self.max_size_bytes,
        )

    async def load_audio(self, file_path: str) -> Tuple[np.ndarray, int]:
        """Load audio file and return audio data and sample rate.

        Uses librosa as primary loader (resamples to `self.target_sr`).
        Performs basic file existence/size check.
        """
        try:
            if not file_path or not os.path.exists(file_path):
                raise AudioProcessingError(f"Audio file not found: {file_path}")

            # size check
            try:
                size = os.path.getsize(file_path)
                if size > self.max_size_bytes:
                    raise AudioProcessingError(f"Audio file too large: {size} bytes (max {self.max_size_bytes})")
            except OSError as oe:
                logger.debug("Could not stat file '%s': %s", file_path, oe)

            # Load (librosa loads and resamples when sr is provided)
            if librosa is not None:
                try:
                    audio_data, sr = librosa.load(file_path, sr=self.target_sr, mono=True)
                    if audio_data is None:
                        raise AudioProcessingError("Librosa returned no audio data")
                    return audio_data, sr
                except Exception as e:  # pragma: no cover - depends on optional dependency
                    logger.warning("librosa.load failed for %s: %s; falling back to soundfile", file_path, e)

            # fallback to soundfile (will not resample)
            if sf is not None:
                try:
                    data, sr = sf.read(file_path, always_2d=False)
                    if data is None:
                        raise AudioProcessingError("soundfile.read returned no data")
                    if getattr(data, "ndim", 0) > 1:
                        data = np.mean(data, axis=1)
                    if sr != self.target_sr:
                        data, sr = self._resample_if_possible(data, sr)
                    return np.asarray(data, dtype="float32"), sr
                except Exception as sf_exc:  # pragma: no cover - depends on optional dependency
                    raise AudioProcessingError(
                        f"Failed to load audio with available backends: {sf_exc}"
                    ) from sf_exc

            raise AudioProcessingError(
                "Audio loading dependencies are unavailable. Install 'librosa' or 'soundfile'."
            )

        except AudioProcessingError:
            # re-raise domain-specific exceptions unchanged
            raise
        except Exception as exc:
            logger.exception("Unexpected error loading audio '%s': %s", file_path, exc)
            raise AudioProcessingError(f"Failed to load audio: {exc}") from exc

    async def save_audio(self, audio_data: np.ndarray, file_path: str, sample_rate: int) -> None:
        """Save audio data to file using soundfile. Creates parent directories as needed."""
        if sf is None:
            raise AudioProcessingError(
                "Saving audio requires the optional 'soundfile' dependency."
            )

        try:
            dir_path = os.path.dirname(file_path) or "."
            os.makedirs(dir_path, exist_ok=True)
            # soundfile expects shape (n_samples,) or (n_samples, n_channels)
            sf.write(file_path, audio_data, int(sample_rate))
        except Exception as e:
            logger.exception("Failed to save audio to %s: %s", file_path, e)
            raise AudioProcessingError(f"Failed to save audio: {e}") from e

    async def validate_audio(self, file_path: str) -> bool:
        """Validate if audio file is suitable for voice cloning.

        Current checks:
        - file exists and size <= max_size_bytes
        - duration between min_duration and max_duration
        - amplitude not near-silent
        """
        try:
            audio_data, sr = await self.load_audio(file_path)

            # Check duration
            duration = len(audio_data) / float(sr) if sr > 0 else 0.0
            if duration < max(3.0, self.min_duration):  # prefer >=3s for voice cloning quality
                logger.info("Audio validation failed: too short (%.2fs)", duration)
                return False
            if duration > self.max_duration:
                logger.info("Audio validation failed: too long (%.2fs)", duration)
                return False

            # Check amplitude (not silent)
            try:
                peak = float(np.max(np.abs(audio_data)))
                if peak < 0.01:
                    logger.info("Audio validation failed: too low amplitude (peak=%.6f)", peak)
                    return False
            except Exception:
                logger.debug("Could not compute amplitude for %s", file_path)

            return True
        except AudioProcessingError as ape:
            logger.info("Audio validation error for %s: %s", file_path, ape)
            return False
        except Exception as e:
            logger.exception("Unexpected error validating audio %s: %s", file_path, e)
            return False

    async def preprocess_audio(self, audio_data: np.ndarray, sample_rate: int) -> np.ndarray:
        """Preprocess audio for model input.

        - Normalize
        - Simple noise gate
        """
        try:
            # Normalize audio to -1..1
            audio_data = self._normalize_audio(audio_data.astype("float32"))

            # Apply basic noise gate
            audio_data = self._apply_noise_gate(audio_data)

            return audio_data
        except Exception as e:
            logger.exception("Failed to preprocess audio: %s", e)
            raise AudioProcessingError(f"Failed to preprocess audio: {e}") from e

    def _apply_noise_gate(self, audio_data: np.ndarray, threshold: float = 0.01) -> np.ndarray:
        """Apply simple noise gate to reduce background noise."""
        try:
            mask = np.abs(audio_data) > threshold
            return audio_data * mask
        except Exception as e:
            logger.debug("Noise gate failed: %s", e)
            return audio_data

    def _normalize_audio(self, audio_data: np.ndarray) -> np.ndarray:
        """Normalize audio data without requiring librosa."""
        if librosa is not None and hasattr(librosa, "util"):
            try:  # pragma: no cover - depends on optional dependency
                return librosa.util.normalize(audio_data)
            except Exception:
                logger.debug("librosa normalization failed; falling back to numpy implementation")

        peak = np.max(np.abs(audio_data)) if audio_data.size > 0 else 0.0
        if peak == 0:
            return audio_data
        return audio_data / peak

    def _resample_if_possible(self, audio_data: np.ndarray, source_sr: int) -> Tuple[np.ndarray, int]:
        """Resample audio if a backend is available; otherwise return original data."""
        if source_sr == self.target_sr:
            return audio_data, source_sr

        if librosa is not None and hasattr(librosa, "resample"):
            try:  # pragma: no cover - depends on optional dependency
                data = librosa.resample(
                    np.asarray(audio_data, dtype="float32"),
                    orig_sr=source_sr,
                    target_sr=self.target_sr,
                )
                return data, self.target_sr
            except Exception:
                logger.debug("librosa.resample failed; falling back to numpy implementation")

        try:
            data = self._numpy_resample(audio_data, source_sr, self.target_sr)
            return data, self.target_sr
        except Exception as exc:
            logger.debug("Numpy resample failed: %s", exc)
            return audio_data, source_sr

    def _numpy_resample(self, audio_data: np.ndarray, source_sr: int, target_sr: int) -> np.ndarray:
        """Simple linear interpolation resampler using NumPy only."""
        if source_sr <= 0 or target_sr <= 0 or audio_data.size == 0:
            return np.asarray(audio_data, dtype="float32")

        audio = np.asarray(audio_data, dtype="float32")
        duration = audio.shape[0] / float(source_sr)
        target_length = max(int(round(duration * target_sr)), 1)

        source_times = np.linspace(0.0, duration, num=audio.shape[0], endpoint=False)
        target_times = np.linspace(0.0, duration, num=target_length, endpoint=False)

        return np.interp(target_times, source_times, audio)
