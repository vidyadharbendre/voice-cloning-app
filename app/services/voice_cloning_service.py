from typing import Dict
from app.services.audio_processor import SimpleAudioProcessor
from app.services.file_manager import LocalFileManager
from app.services.tts_engine import DummyTTS


class VoiceCloningService:
    def __init__(self,
                 audio_processor: SimpleAudioProcessor = None,
                 file_manager: LocalFileManager = None,
                 tts: DummyTTS = None):
        self.audio_processor = audio_processor or SimpleAudioProcessor()
        self.file_manager = file_manager or LocalFileManager()
        self.tts = tts or DummyTTS()

    def start_clone(self, source_audio_url: str, target_name: str) -> Dict:
        processed = self.audio_processor.prepare(source_audio_url)
        features = self.audio_processor.extract_features(processed)
        # placeholder: run actual cloning model here
        # save placeholder output
        out_path = self.tts.synthesize("This is a dummy clone.", {"name": target_name})
        saved = self.file_manager.save(out_path, f"{target_name}.wav")
        return {"job_id": "job-123", "status": "completed", "output": saved}
