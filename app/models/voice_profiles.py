# ================================
# VOICE PROFILE MANAGEMENT SYSTEM
# Record, Store, and Manage Individual User Voices
# ================================

# ================================
# FILE: app/models/voice_profiles.py
# ================================

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
import uuid

class VoiceProfileStatus(str, Enum):
    """Status of voice profile"""
    RECORDING = "recording"
    PROCESSING = "processing" 
    READY = "ready"
    FAILED = "failed"

class VoiceQuality(str, Enum):
    """Voice quality levels"""
    EXCELLENT = "excellent"  # 90-100 quality score
    GOOD = "good"           # 75-89 quality score  
    FAIR = "fair"           # 60-74 quality score
    POOR = "poor"           # Below 60 quality score

class RecordingStep(BaseModel):
    """Individual recording step in voice training"""
    step_number: int
    text_prompt: str
    audio_file_id: Optional[str] = None
    duration: Optional[float] = None
    quality_score: Optional[float] = None
    completed: bool = False
    recording_url: Optional[str] = None

class VoiceProfile(BaseModel):
    """Complete voice profile for a user"""
    profile_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    profile_name: str
    description: Optional[str] = None
    status: VoiceProfileStatus = VoiceProfileStatus.RECORDING
    quality: Optional[VoiceQuality] = None
    
    # Recording steps
    recording_steps: List[RecordingStep] = []
    total_steps: int = 10  # Default number of sentences to record
    completed_steps: int = 0
    
    # Voice characteristics
    voice_embedding: Optional[str] = None  # Path to voice embedding file
    sample_rate: int = 22050
    total_duration: Optional[float] = None
    
    # Quality metrics
    overall_quality_score: Optional[float] = None
    clarity_score: Optional[float] = None
    consistency_score: Optional[float] = None
    noise_level: Optional[float] = None
    
    # Usage statistics
    times_used: int = 0
    last_used: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Settings
    is_public: bool = False
    allow_cloning: bool = True
    tags: List[str] = []

class VoiceRecordingRequest(BaseModel):
    """Request to start voice recording session"""
    profile_name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=200)
    total_steps: int = Field(default=10, ge=5, le=20)  # 5-20 sentences
    language: str = "en"

class VoiceRecordingStepRequest(BaseModel):
    """Request to submit a recording step"""
    profile_id: str
    step_number: int
    audio_data: str  # Base64 encoded audio or file upload

class VoiceUsageRequest(BaseModel):
    """Request to use a voice profile for synthesis"""
    profile_id: str
    text: str = Field(..., min_length=1, max_length=1000)
    language: str = "en"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    emotion: Optional[str] = None

class VoiceProfileListResponse(BaseModel):
    """Response listing user's voice profiles"""
    profiles: List[VoiceProfile]
    total_count: int
    
class VoiceRecordingSessionResponse(BaseModel):
    """Response for recording session"""
    success: bool
    profile_id: str
    current_step: int
    total_steps: int
    next_prompt: Optional[str] = None
    progress_percentage: float
    message: str