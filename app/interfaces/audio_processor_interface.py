# ================================
# FILE: app/interfaces/audio_processor_interface.py
# ================================

from abc import ABC, abstractmethod
from typing import Tuple, Optional
import numpy as np

class IAudioProcessor(ABC):
    """Interface for audio processing operations following Interface Segregation Principle"""
    
    @abstractmethod
    async def load_audio(self, file_path: str) -> Tuple[np.ndarray, int]:
        """Load audio file and return audio data and sample rate"""
        pass
    
    @abstractmethod
    async def save_audio(self, audio_data: np.ndarray, file_path: str, sample_rate: int) -> None:
        """Save audio data to file"""
        pass
    
    @abstractmethod
    async def validate_audio(self, file_path: str) -> bool:
        """Validate if audio file is suitable for voice cloning"""
        pass
    
    @abstractmethod
    async def preprocess_audio(self, audio_data: np.ndarray, sample_rate: int) -> np.ndarray:
        """Preprocess audio for model input"""
        pass