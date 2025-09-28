from fastapi import APIRouter, Depends, HTTPException
from app.models.schemas import CloneRequest, CloneResponse
from .dependencies import get_voice_cloning_service
from app.services.voice_cloning_service import VoiceCloningService

router = APIRouter()

@router.post("/clone", response_model=CloneResponse)
def clone_voice(payload: CloneRequest, svc: VoiceCloningService = Depends(get_voice_cloning_service)):
    try:
        result = svc.start_clone(payload.source_audio_url, payload.target_speaker_name or "unknown")
        return {"job_id": result["job_id"], "status": result["status"], "output_url": result.get("output")}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
