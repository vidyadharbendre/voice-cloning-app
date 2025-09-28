from app.core.config import Settings
from app.services.voice_cloning_service import VoiceCloningService

def get_settings() -> Settings:
    return Settings()

def get_voice_cloning_service() -> VoiceCloningService:
    return VoiceCloningService()
