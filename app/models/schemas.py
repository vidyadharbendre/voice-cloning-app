# Models package

# ================================
# FILE: app/models/schemas.py
# ================================

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from enum import Enum

class LanguageEnum(str, Enum):
    """Supported languages enumeration"""
    EN = "en"
    ES = "es" 
    FR = "fr"
    DE = "de"
    IT = "it"
    PT = "pt"
    PL = "pl"
    TR = "tr"
    RU = "ru"
    NL = "nl"
    CS = "cs"
    AR = "ar"
    ZH = "zh"
    JA = "ja"
    HU = "hu"
    KO = "ko"
    HI = "hi"

class TTSRequest(BaseModel):
    """Request model for text-to-speech synthesis"""
    
    text: str = Field(..., min_length=1, max_length=1000, description="Text to synthesize")
    language: LanguageEnum = Field(default=LanguageEnum.EN, description="Target language")
    speaker_wav_path: Optional[str] = Field(default=None, description="Path to speaker reference audio")
    speed: float = Field(default=1.0, ge=0.5, le=2.0, description="Speech speed multiplier")
    
    @validator('text')
    def validate_text(cls, v):
        if not v.strip():
            raise ValueError('Text cannot be empty')
        return v.strip()

class VoiceCloningRequest(BaseModel):
    """Request model for voice cloning"""
    
    text: str = Field(..., min_length=1, max_length=1000, description="Text to synthesize")
    language: LanguageEnum = Field(default=LanguageEnum.EN, description="Target language")
    reference_audio_id: str = Field(..., description="ID of uploaded reference audio")
    
class TTSResponse(BaseModel):
    """Response model for TTS operations"""
    
    success: bool
    audio_file_path: Optional[str] = None
    duration: Optional[float] = None
    message: str
    error_code: Optional[str] = None

class VoiceCloningResponse(BaseModel):
    """Response model for voice cloning operations"""
    
    success: bool
    audio_file_path: Optional[str] = None
    cloned_voice_id: Optional[str] = None
    similarity_score: Optional[float] = None
    message: str
    error_code: Optional[str] = None

class AudioUploadResponse(BaseModel):
    """Response model for audio upload"""
    
    success: bool
    file_id: str
    filename: str
    duration: Optional[float] = None
    message: str

class HealthResponse(BaseModel):
    """Health check response model"""
    
    status: str
    version: str
    model_loaded: bool
    gpu_available: bool
