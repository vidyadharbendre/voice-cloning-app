# app/core/config.py
"""
Configuration Module
Application settings and configuration with comprehensive attribute support
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any


class Settings:
    """Application settings with both uppercase and lowercase attribute support"""

    # Application
    APP_NAME: str = os.getenv("APP_NAME", "Voice Cloning API")
    app_name: str = os.getenv("APP_NAME", "Voice Cloning API")
    VERSION: str = os.getenv("VERSION", "1.0.0")
    version: str = os.getenv("VERSION", "1.0.0")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    host: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    port: int = int(os.getenv("PORT", "8000"))

    # TTS Model
    TTS_MODEL_NAME: str = os.getenv(
        "TTS_MODEL_NAME",
        "tts_models/multilingual/multi-dataset/xtts_v2",
    )
    default_model: str = os.getenv(
        "DEFAULT_MODEL",
        os.getenv("TTS_MODEL_NAME", "tts_models/multilingual/multi-dataset/xtts_v2"),
    )
    USE_GPU: bool = os.getenv("USE_GPU", "true").lower() == "true"
    use_gpu: bool = os.getenv("USE_GPU", "true").lower() == "true"

    # Device selection
    device: Optional[str] = os.getenv("DEVICE")
    DEVICE: Optional[str] = os.getenv("DEVICE")

    # Language
    default_language: str = os.getenv("DEFAULT_LANGUAGE", "en")
    DEFAULT_LANGUAGE: str = os.getenv("DEFAULT_LANGUAGE", "en")
    SUPPORTED_LANGUAGES: List[str] = [
        "en",
        "es",
        "fr",
        "de",
        "it",
        "pt",
        "pl",
        "tr",
        "ru",
        "nl",
        "cs",
        "ar",
        "zh-cn",
        "ja",
        "ko",
        "hu",
    ]
    supported_languages: List[str] = SUPPORTED_LANGUAGES

    # Storage
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")
    upload_dir: str = os.getenv("UPLOAD_DIR", "uploads")
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "output")
    output_dir: str = os.getenv("OUTPUT_DIR", "output")
    VOICE_PROFILES_DIR: str = os.getenv("VOICE_PROFILES_DIR", "voice_profiles")
    voice_profiles_dir: str = os.getenv("VOICE_PROFILES_DIR", "voice_profiles")
    TEMP_DIR: str = os.getenv("TEMP_DIR", "temp")
    temp_dir: str = os.getenv("TEMP_DIR", "temp")

    # File Limits
    MAX_UPLOAD_SIZE: int = int(os.getenv("MAX_UPLOAD_SIZE", str(50 * 1024 * 1024)))
    max_upload_size: int = MAX_UPLOAD_SIZE
    max_upload_size_mb: int = MAX_UPLOAD_SIZE // (1024 * 1024)

    MAX_TEXT_LENGTH: int = int(os.getenv("MAX_TEXT_LENGTH", "5000"))
    max_text_length: int = MAX_TEXT_LENGTH

    MAX_AUDIO_DURATION: int = int(os.getenv("MAX_AUDIO_DURATION", "300"))
    max_audio_duration: int = MAX_AUDIO_DURATION
    MAX_AUDIO_DURATION_SECONDS: int = MAX_AUDIO_DURATION

    # Audio Settings
    ALLOWED_AUDIO_FORMATS: List[str] = ["wav", "mp3", "ogg", "flac", "m4a"]
    allowed_audio_formats: List[str] = ALLOWED_AUDIO_FORMATS

    # canonical name for sample rate used by new code
    DEFAULT_SAMPLE_RATE: int = int(os.getenv("DEFAULT_SAMPLE_RATE", str(22050)))
    default_sample_rate: int = int(os.getenv("DEFAULT_SAMPLE_RATE", str(22050)))

    # Backwards-compatible alias for older code that expects `settings.sample_rate`
    @property
    def sample_rate(self) -> int:  # pragma: no cover - trivial accessor
        """
        Backwards-compatible accessor. New code should use `default_sample_rate`.
        """
        return getattr(self, "default_sample_rate", getattr(self, "DEFAULT_SAMPLE_RATE", 22050))

    # Add hop_length / win_length defaults (requested by audio processing code)
    HOP_LENGTH: int = int(os.getenv("HOP_LENGTH", "256"))
    hop_length: int = int(os.getenv("HOP_LENGTH", "256"))

    WIN_LENGTH: int = int(os.getenv("WIN_LENGTH", "1024"))
    win_length: int = int(os.getenv("WIN_LENGTH", "1024"))

    MIN_AUDIO_DURATION: float = float(os.getenv("MIN_AUDIO_DURATION", "0.5"))
    min_audio_duration: float = float(os.getenv("MIN_AUDIO_DURATION", "0.5"))

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    rate_limit_enabled: bool = RATE_LIMIT_ENABLED
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    rate_limit_requests: int = RATE_LIMIT_REQUESTS
    RATE_LIMIT_PERIOD: int = int(os.getenv("RATE_LIMIT_PERIOD", "3600"))
    rate_limit_period: int = RATE_LIMIT_PERIOD

    # Health Check
    health_check_text: str = os.getenv("HEALTH_CHECK_TEXT", "Health check")
    health_check_speaker: Optional[str] = os.getenv("HEALTH_CHECK_SPEAKER")
    health_check_ref_wav: Optional[str] = os.getenv("HEALTH_CHECK_REF_WAV")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    log_level: str = LOG_LEVEL
    LOG_DIR: str = os.getenv("LOG_DIR", "logs")
    log_dir: str = LOG_DIR

    # Background Tasks
    CLEANUP_INTERVAL: int = int(os.getenv("CLEANUP_INTERVAL", "3600"))
    cleanup_interval: int = CLEANUP_INTERVAL
    FILE_MAX_AGE_HOURS: int = int(os.getenv("FILE_MAX_AGE_HOURS", "24"))
    file_max_age_hours: int = FILE_MAX_AGE_HOURS

    # Security
    CORS_ORIGINS: List[str] = os.getenv("CORS_ORIGINS", "*").split(",")
    cors_origins: List[str] = CORS_ORIGINS

    # API Settings
    api_prefix: str = os.getenv("API_PREFIX", "/api/v1")
    API_PREFIX: str = api_prefix

    # Description
    description: str = "Production-ready voice cloning API with XTTS"

    # ----------------------------
    # New TTS-related configuration
    # ----------------------------
    # Path to an example WAV to auto-register as a default speaker (optional).
    # Example: "/opt/app/data/default_speaker.wav"
    TTS_DEFAULT_SPEAKER_WAV: Optional[str] = os.getenv("TTS_DEFAULT_SPEAKER_WAV")
    tts_default_speaker_wav: Optional[str] = os.getenv("TTS_DEFAULT_SPEAKER_WAV")

    # Predefined speaker id to use as default (if known). Could be numeric or string.
    TTS_DEFAULT_SPEAKER_ID: Optional[str] = os.getenv("TTS_DEFAULT_SPEAKER_ID")
    tts_default_speaker_id: Optional[str] = os.getenv("TTS_DEFAULT_SPEAKER_ID")

    # Allow fallback attempt when no speaker is available (may fail for strict models).
    TTS_ALLOW_FALLBACK_WITHOUT_SPEAKER: bool = os.getenv("TTS_ALLOW_FALLBACK_WITHOUT_SPEAKER", "false").lower() == "true"
    tts_allow_fallback_without_speaker: bool = os.getenv("TTS_ALLOW_FALLBACK_WITHOUT_SPEAKER", "false").lower() == "true"

    # Trust checkpoints to permit full unpickling fallback (weights_only=False).
    # Keeps backward compatibility with previously used name `tts_trust_checkpoints`.
    TTS_TRUST_CHECKPOINTS: bool = os.getenv("TTS_TRUST_CHECKPOINTS", "false").lower() == "true"
    tts_trust_checkpoints: bool = os.getenv("TTS_TRUST_CHECKPOINTS", "false").lower() == "true"

    # Backwards-compatible lowercase aliases for newer keys (so code can use settings.tts_*)
    tts_default_speaker_wav = tts_default_speaker_wav
    tts_default_speaker_id = tts_default_speaker_id
    tts_allow_fallback_without_speaker = tts_allow_fallback_without_speaker
    tts_trust_checkpoints = tts_trust_checkpoints

    @classmethod
    def create_directories(cls) -> None:
        """Create necessary directories"""
        for dir_path in [
            cls.UPLOAD_DIR,
            cls.OUTPUT_DIR,
            cls.VOICE_PROFILES_DIR,
            cls.TEMP_DIR,
            cls.LOG_DIR,
        ]:
            Path(dir_path).mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_settings_dict(cls) -> Dict[str, Any]:
        """Get all settings as dictionary"""
        result = {}
        for key in dir(cls):
            if key.startswith("_"):
                continue
            val = getattr(cls, key)
            if callable(val):
                continue
            result[key] = val
        return result

    def __getattr__(self, name: str):
        """
        Fallback for missing attributes - try uppercase/lowercase variants.
        This helps with compatibility when code uses different naming conventions.
        """
        # Try uppercase version
        upper_name = name.upper()
        if hasattr(Settings, upper_name):
            return getattr(Settings, upper_name)

        # Try lowercase version
        lower_name = name.lower()
        if hasattr(Settings, lower_name):
            return getattr(Settings, lower_name)

        # Helpful message listing available public attributes (non-private)
        public_keys = [k for k in dir(Settings) if not k.startswith("_")]
        raise AttributeError(
            f"Settings has no attribute '{name}'. Available settings: {', '.join(public_keys)}"
        )


# Global settings instance
settings = Settings()

# Create directories on import
settings.create_directories()
