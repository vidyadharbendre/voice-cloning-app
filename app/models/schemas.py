from pydantic import BaseModel
from typing import Optional


class CloneRequest(BaseModel):
    source_audio_url: str
    target_speaker_name: Optional[str] = None
    style: Optional[str] = "neutral"


class CloneResponse(BaseModel):
    job_id: str
    status: str
    output_url: Optional[str] = None
