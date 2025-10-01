# ================================
# FILE: app/api/dependencies.py
# ================================

from fastapi import Depends
from app.services.tts_engine import XTTSTTSEngine
from app.services.audio_processor import AudioProcessor
from app.services.file_manager import FileManager
from app.services.voice_cloning_service import VoiceCloningService

# Dependency injection following Dependency Inversion Principle
def get_tts_engine() -> XTTSTTSEngine:
    return XTTSTTSEngine()

def get_audio_processor() -> AudioProcessor:
    return AudioProcessor()

def get_file_manager() -> FileManager:
    return FileManager()

def get_voice_cloning_service(
    tts_engine: XTTSTTSEngine = Depends(get_tts_engine),
    audio_processor: AudioProcessor = Depends(get_audio_processor),
    file_manager: FileManager = Depends(get_file_manager)
) -> VoiceCloningService:
    return VoiceCloningService(tts_engine, audio_processor, file_manager)