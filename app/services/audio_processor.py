from pathlib import Path
from . import __name__ as _pkg
from typing import Dict
from app.interfaces.audio_processor_interface import AudioProcessorInterface


class SimpleAudioProcessor(AudioProcessorInterface):
    def prepare(self, source: str) -> Path:
        # placeholder: download/normalize/convert to WAV, etc.
        # raise meaningful exceptions on failure
        return Path(source)

    def extract_features(self, audio_path: Path) -> Dict:
        # placeholder feature extraction
        return {"duration_sec": 0.0}
