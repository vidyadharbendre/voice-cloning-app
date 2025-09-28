from abc import ABC, abstractmethod
from pathlib import Path


class TTSInterface(ABC):
    @abstractmethod
    def synthesize(self, text: str, voice_profile: dict) -> Path:
        """Synthesize text to audio and return the file path."""
        raise NotImplementedError
