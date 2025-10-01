# ================================
# FILE: app/api/routes.py
# ================================

import os
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from app.api.dependencies import get_voice_cloning_service, get_file_manager
from app.models.schemas import (
    TTSRequest, VoiceCloningRequest, TTSResponse, 
    VoiceCloningResponse, AudioUploadResponse, HealthResponse
)
from app.services.voice_cloning_service import VoiceCloningService
from app.services.file_manager import FileManager
from app.core.config import settings
import torch

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        version=settings.version,
        model_loaded=True,  # TODO: Check actual model status
        gpu_available=torch.cuda.is_available()
    )

@router.post("/upload-audio", response_model=AudioUploadResponse)
async def upload_audio(
    file: UploadFile = File(...),
    file_manager: FileManager = Depends(get_file_manager)
):
    """Upload reference audio for voice cloning"""
    try:
        file_id = await file_manager.save_upload(file)
        return AudioUploadResponse(
            success=True,
            file_id=file_id,
            filename=file.filename,
            message="Audio file uploaded successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/synthesize", response_model=TTSResponse)
async def synthesize_speech(
    request: TTSRequest,
    service: VoiceCloningService = Depends(get_voice_cloning_service)
):
    """Synthesize speech from text"""
    return await service.synthesize_speech(request)

@router.post("/clone-voice", response_model=VoiceCloningResponse)
async def clone_voice(
    request: VoiceCloningRequest,
    service: VoiceCloningService = Depends(get_voice_cloning_service)
):
    """Clone voice from reference audio"""
    return await service.clone_voice(request)

@router.get("/download/{filename}")
async def download_audio(filename: str):
    """Download generated audio file"""
    file_path = os.path.join(settings.output_dir, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        media_type="audio/wav",
        filename=filename
    )

@router.delete("/cleanup")
async def cleanup_files(
    max_age_hours: int = 24,
    file_manager: FileManager = Depends(get_file_manager)
):
    """Clean up old files"""
    deleted_count = await file_manager.cleanup_old_files(max_age_hours)
    return {"message": f"Deleted {deleted_count} old files"}