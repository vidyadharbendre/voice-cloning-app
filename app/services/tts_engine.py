from pathlib import Path
from app.interfaces.tts_interface import TTSInterface


class DummyTTS(TTSInterface):
    def synthesize(self, text: str, voice_profile: dict) -> Path:
        # Placeholder implementation
        out = Path("/tmp/dummy_tts.wav")
        out.write_bytes(b"")  # empty placeholder
        return out
