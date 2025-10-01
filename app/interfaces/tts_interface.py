# ================================
# FILE: app/interfaces/tts_interface.py
# ================================

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class ITTSEngine(ABC):
    """Interface for TTS engines following Interface Segregation Principle"""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the TTS engine"""
        pass
    
    @abstractmethod
    async def synthesize(self, text: str, language: str, output_path: str, **kwargs) -> Dict[str, Any]:
        """Synthesize text to speech"""
        pass
    
    @abstractmethod
    async def clone_voice(self, text: str, reference_audio_path: str, output_path: str, language: str, **kwargs) -> Dict[str, Any]:
        """Clone voice from reference audio"""
        pass
    
    @abstractmethod
    def is_initialized(self) -> bool:
        """Check if engine is initialized"""
        pass
