import io
import os
import tempfile
import wave
import uuid
import pytest
from fastapi.testclient import TestClient

# Import the app (adjust path if your project structure differs)
from app.main import app

# --- Helpers: generate a tiny valid WAV file in-memory ---
def generate_silent_wav_bytes(duration_seconds: float = 1.0, sample_rate: int = 16000) -> bytes:
    """
    Generate a short silent 16-bit PCM WAV file as bytes.
    This avoids extra dependencies like numpy and is enough for upload testing.
    """
    n_channels = 1
    sampwidth = 2  # bytes (16-bit)
    n_frames = int(duration_seconds * sample_rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(n_channels)
        w.setsampwidth(sampwidth)
        w.setframerate(sample_rate)
        # write silence (zeros)
        w.writeframes(b"\x00" * n_frames * n_channels * sampwidth)
    return buf.getvalue()


# --- Mock service implementations (async methods to match routes) ---
class MockVoiceProfileService:
    def __init__(self, tmp_dir: str):
        self.tmp_dir = tmp_dir
        self.profiles = {}
        # create one ready profile entry to list and use
        pid = "profile-1234"
        sample_path = os.path.join(tmp_dir, f"sample_{pid}.wav")
        # write a tiny sample file
        with open(sample_path, "wb") as f:
            f.write(generate_silent_wav_bytes(0.2))
        self.profiles[pid] = {
            "profile_id": pid,
            "profile_name": "Mock Voice",
            "created_at": "2025-01-01T00:00:00Z",
            "status": "ready",
            "quality": "high",
            "voice_embedding_path": sample_path,
            "times_used": 0,
        }

    async def start_recording_session(self, user_id, request_data):
        # return an object/dict acceptable as VoiceRecordingSessionResponse
        session = {
            "success": True,
            "profile_id": f"session-{uuid.uuid4().hex[:8]}",
            "next_prompt": "Please read this short sentence.",
            "current_step": 1,
            "total_steps": 3,
            "progress_percentage": 0,
        }
        return session

    async def submit_recording_step(self, user_id, step_request, audio_path):
        # pretend we accepted and advanced
        resp = {
            "success": True,
            "profile_id": step_request.profile_id,
            "current_step": step_request.step_number + 1,
            "next_prompt": "Next prompt text.",
            "progress_percentage": min(100, (step_request.step_number + 1) * 33),
        }
        return resp

    async def get_user_profiles(self, user_id):
        profiles = list(self.profiles.values())
        return {"success": True, "total_count": len(profiles), "profiles": profiles}

    async def use_voice_profile(self, user_id, usage_request):
        # Return voice metadata; routes will call TTS service afterwards
        p = self.profiles.get(usage_request.profile_id)
        if not p:
            raise Exception("profile not found")
        # echo text requested so TTS receives it (route takes text from voice_data if present)
        return {
            "profile_id": p["profile_id"],
            "profile_name": p["profile_name"],
            "voice_embedding_path": p["voice_embedding_path"],
            "text": getattr(usage_request, "text", "hello from mock"),
            "language": "en",
            "speed": 1.0,
            "quality": p.get("quality", "unknown"),
        }

    async def delete_voice_profile(self, user_id, profile_id):
        if profile_id in self.profiles:
            del self.profiles[profile_id]
            return True
        return False

    async def get_profile_metadata(self, user_id, profile_id):
        p = self.profiles.get(profile_id)
        if not p:
            return None
        return p


class MockTTSService:
    class Result:
        def __init__(self, audio_file_path):
            self.success = True
            self.audio_file_path = audio_file_path

        def dict(self):
            return {"success": True, "audio_file_path": self.audio_file_path}

    async def synthesize_speech(self, tts_request):
        # write a small file to disk and return path
        tmp = tempfile.gettempdir()
        out_path = os.path.join(tmp, f"tts_out_{uuid.uuid4().hex[:8]}.wav")
        with open(out_path, "wb") as f:
            f.write(generate_silent_wav_bytes(0.2))
        return MockTTSService.Result(out_path)


# --- Pytest fixtures to override dependencies ---
@pytest.fixture
def client():
    tmp_dir = tempfile.mkdtemp(prefix="vp_test_")
    mock_svc = MockVoiceProfileService(tmp_dir=tmp_dir)
    mock_tts = MockTTSService()

    # override dependencies that routes use
    from app.api.voice_profile_routes import get_voice_profile_service, get_voice_cloning_service

    # the factory in the app expects signature (audio_processor=..., request=...), so make override accept those
    def svc_override(audio_processor=None, request=None):
        return mock_svc

    def tts_override():
        return mock_tts

    app.dependency_overrides[get_voice_profile_service] = svc_override
    app.dependency_overrides[get_voice_cloning_service] = tts_override

    with TestClient(app) as c:
        yield c

    # teardown
    try:
        # remove tmp_dir and any created files
        for root, dirs, files in os.walk(tmp_dir):
            for f in files:
                try:
                    os.unlink(os.path.join(root, f))
                except Exception:
                    pass
        os.rmdir(tmp_dir)
    except Exception:
        pass


# --- Tests ---
def test_start_recording_html_redirect(client: TestClient):
    body = {"profile_name": "TestVoice", "description": "desc", "total_steps": 3}
    resp = client.post("/api/v1/voice-profiles/profiles/start-recording", json=body, headers={"accept": "text/html"}, allow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers.get("location") == "/voice-recorder"


def test_start_recording_json(client: TestClient):
    body = {"profile_name": "TestVoice", "description": "desc", "total_steps": 3}
    resp = client.post("/api/v1/voice-profiles/profiles/start-recording", json=body, headers={"accept": "application/json"})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True
    assert "profile_id" in data


def test_submit_recording_step_upload(client: TestClient):
    # Prepare small wav bytes
    wav_bytes = generate_silent_wav_bytes(0.5)
    files = {
        "audio_file": ("sample.wav", wav_bytes, "audio/wav")
    }
    data = {
        "profile_id": "profile-1234",
        "step_number": "1",
    }
    resp = client.post("/api/v1/voice-profiles/profiles/submit-recording", files=files, data=data)
    assert resp.status_code == 200
    j = resp.json()
    assert j.get("success") is True


def test_list_profiles(client: TestClient):
    resp = client.get("/api/v1/voice-profiles/profiles")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("total_count", 0) >= 1
    assert isinstance(data.get("profiles"), list)


def test_use_voice_and_synthesize(client: TestClient):
    body = {"profile_id": "profile-1234", "text": "Hello world"}
    resp = client.post("/api/v1/voice-profiles/profiles/use-voice", json=body)
    assert resp.status_code == 200
    data = resp.json()
    # TTS mock writes audio_file_path to tmp and route returns it inside result
    assert data.get("success") is True or "audio_file_path" in data


def test_get_sample_and_delete(client: TestClient):
    # sample should exist for profile-1234 per mock
    resp = client.get("/api/v1/voice-profiles/profiles/profile-1234/sample")
    assert resp.status_code == 200
    # then delete
    resp2 = client.delete("/api/v1/voice-profiles/profiles/profile-1234")
    assert resp2.status_code == 200
    j = resp2.json()
    assert j.get("success") is True
    # subsequent sample should now 404 or raise ValidationException -> mapped to 500-ish wrapper; just ensure not 200
    resp3 = client.get("/api/v1/voice-profiles/profiles/profile-1234/sample")
    assert resp3.status_code != 200
