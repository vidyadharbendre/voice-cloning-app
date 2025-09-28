from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict


class AudioProcessorInterface(ABC):
    @abstractmethod
    def prepare(self, source: str) -> Path:
        """Prepare and normalize an input audio file. Return path to processed file."""
        raise NotImplementedError

    @abstractmethod
    def extract_features(self, audio_path: Path) -> Dict:
        """Extract features required by the cloning model."""
        raise NotImplementedError
