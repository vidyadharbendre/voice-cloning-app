#!/usr/bin/env bash
# create_voice_cloning_scaffold.sh
# Creates a voice-cloning FastAPI project scaffold (safe: will not overwrite existing files)
set -euo pipefail

ROOT="voice-cloning-app"
echo "Creating scaffold under ./${ROOT}"

# helper: create dir if not exists
mkd() {
  if [ ! -d "$1" ]; then
    mkdir -p "$1"
    echo "  created dir: $1"
  else
    echo "  exists dir: $1 (skipping)"
  fi
}

# helper: create file if not exists (with heredoc content)
create_file() {
  local path="$1"
  local content="$2"
  if [ -e "$path" ]; then
    echo "  exists file: $path (skipping)"
  else
    mkdir -p "$(dirname "$path")"
    cat > "$path" <<'PY'
'"$content"' 
PY
    # The above line uses a trick — the actual heredoc is constructed below.
  fi
}

# We'll build files using explicit cat blocks to avoid complexity with embedded single quotes.
mkd "${ROOT}/app/core"
mkd "${ROOT}/app/models"
mkd "${ROOT}/app/interfaces"
mkd "${ROOT}/app/services"
mkd "${ROOT}/app/api"
mkd "${ROOT}/tests"
mkd "${ROOT}/docker"
mkd "${ROOT}/scripts"
mkd "${ROOT}/notebooks"
mkd "${ROOT}/docs"

# ---- create files with content ----
# app/__init__.py
if [ ! -e "${ROOT}/app/__init__.py" ]; then
cat > "${ROOT}/app/__init__.py" <<'PY'
# app package
PY
echo "  created file: ${ROOT}/app/__init__.py"
else
  echo "  exists file: ${ROOT}/app/__init__.py (skipping)"
fi

# app/main.py (FastAPI bootstrap with basic error handling)
if [ ! -e "${ROOT}/app/main.py" ]; then
cat > "${ROOT}/app/main.py" <<'PY'
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from .api.routes import router as api_router
from .core.config import Settings

settings = Settings()

app = FastAPI(title="voice-cloning-app", version="0.1.0")

app.include_router(api_router, prefix="/api/v1")

@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "service": "voice-cloning-app"}

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # RFC 9457 friendly problem+json
    return JSONResponse(status_code=exc.status_code, content={
        "type": "about:blank",
        "title": exc.detail or "HTTP Error",
        "status": exc.status_code,
        "instance": str(request.url.path)
    })

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={
        "type": "about:blank",
        "title": "Internal Server Error",
        "status": 500,
        "detail": str(exc),
        "instance": str(request.url.path)
    })
PY
echo "  created file: ${ROOT}/app/main.py"
else
  echo "  exists file: ${ROOT}/app/main.py (skipping)"
fi

# app/core/config.py (pydantic settings)
if [ ! -e "${ROOT}/app/core/config.py" ]; then
cat > "${ROOT}/app/core/config.py" <<'PY'
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    APP_NAME: str = Field("voice-cloning-app", env="APP_NAME")
    STORAGE_PATH: str = Field("./storage", env="STORAGE_PATH")
    HOST: str = Field("0.0.0.0", env="HOST")
    PORT: int = Field(8000, env="PORT")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
PY
echo "  created file: ${ROOT}/app/core/config.py"
else
  echo "  exists file: ${ROOT}/app/core/config.py (skipping)"
fi

# app/core/exceptions.py
if [ ! -e "${ROOT}/app/core/exceptions.py" ]; then
cat > "${ROOT}/app/core/exceptions.py" <<'PY'
class VoiceCloningError(Exception):
    """Base exception for voice cloning app."""
    pass
PY
echo "  created file: ${ROOT}/app/core/exceptions.py"
else
  echo "  exists file: ${ROOT}/app/core/exceptions.py (skipping)"
fi

# app/models/schemas.py
if [ ! -e "${ROOT}/app/models/schemas.py" ]; then
cat > "${ROOT}/app/models/schemas.py" <<'PY'
from pydantic import BaseModel
from typing import Optional


class CloneRequest(BaseModel):
    source_audio_url: str
    target_speaker_name: Optional[str] = None
    style: Optional[str] = "neutral"


class CloneResponse(BaseModel):
    job_id: str
    status: str
    output_url: Optional[str] = None
PY
echo "  created file: ${ROOT}/app/models/schemas.py"
else
  echo "  exists file: ${ROOT}/app/models/schemas.py (skipping)"
fi

# app/interfaces/audio_processor_interface.py
if [ ! -e "${ROOT}/app/interfaces/audio_processor_interface.py" ]; then
cat > "${ROOT}/app/interfaces/audio_processor_interface.py" <<'PY'
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
PY
echo "  created file: ${ROOT}/app/interfaces/audio_processor_interface.py"
else
  echo "  exists file: ${ROOT}/app/interfaces/audio_processor_interface.py (skipping)"
fi

# app/interfaces/tts_interface.py
if [ ! -e "${ROOT}/app/interfaces/tts_interface.py" ]; then
cat > "${ROOT}/app/interfaces/tts_interface.py" <<'PY'
from abc import ABC, abstractmethod
from pathlib import Path


class TTSInterface(ABC):
    @abstractmethod
    def synthesize(self, text: str, voice_profile: dict) -> Path:
        """Synthesize text to audio and return the file path."""
        raise NotImplementedError
PY
echo "  created file: ${ROOT}/app/interfaces/tts_interface.py"
else
  echo "  exists file: ${ROOT}/app/interfaces/tts_interface.py (skipping)"
fi

# app/interfaces/file_manager_interface.py
if [ ! -e "${ROOT}/app/interfaces/file_manager_interface.py" ]; then
cat > "${ROOT}/app/interfaces/file_manager_interface.py" <<'PY'
from abc import ABC, abstractmethod
from pathlib import Path


class FileManagerInterface(ABC):
    @abstractmethod
    def save(self, src: Path, dest_name: str) -> str:
        """Save file to storage and return URL/path."""
        raise NotImplementedError

    @abstractmethod
    def get(self, name: str) -> Path:
        raise NotImplementedError
PY
echo "  created file: ${ROOT}/app/interfaces/file_manager_interface.py"
else
  echo "  exists file: ${ROOT}/app/interfaces/file_manager_interface.py (skipping)"
fi

# app/services/audio_processor.py
if [ ! -e "${ROOT}/app/services/audio_processor.py" ]; then
cat > "${ROOT}/app/services/audio_processor.py" <<'PY'
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
PY
echo "  created file: ${ROOT}/app/services/audio_processor.py"
else
  echo "  exists file: ${ROOT}/app/services/audio_processor.py (skipping)"
fi

# app/services/tts_engine.py
if [ ! -e "${ROOT}/app/services/tts_engine.py" ]; then
cat > "${ROOT}/app/services/tts_engine.py" <<'PY'
from pathlib import Path
from app.interfaces.tts_interface import TTSInterface


class DummyTTS(TTSInterface):
    def synthesize(self, text: str, voice_profile: dict) -> Path:
        # Placeholder implementation
        out = Path("/tmp/dummy_tts.wav")
        out.write_bytes(b"")  # empty placeholder
        return out
PY
echo "  created file: ${ROOT}/app/services/tts_engine.py"
else
  echo "  exists file: ${ROOT}/app/services/tts_engine.py (skipping)"
fi

# app/services/file_manager.py
if [ ! -e "${ROOT}/app/services/file_manager.py" ]; then
cat > "${ROOT}/app/services/file_manager.py" <<'PY'
from pathlib import Path
from app.interfaces.file_manager_interface import FileManagerInterface


class LocalFileManager(FileManagerInterface):
    def __init__(self, root: Path = Path("./storage")):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, src: Path, dest_name: str) -> str:
        dest = self.root / dest_name
        src.replace(dest)
        return str(dest)

    def get(self, name: str) -> Path:
        p = self.root / name
        if not p.exists():
            raise FileNotFoundError(name)
        return p
PY
echo "  created file: ${ROOT}/app/services/file_manager.py"
else
  echo "  exists file: ${ROOT}/app/services/file_manager.py (skipping)"
fi

# app/services/voice_cloning_service.py
if [ ! -e "${ROOT}/app/services/voice_cloning_service.py" ]; then
cat > "${ROOT}/app/services/voice_cloning_service.py" <<'PY'
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
PY
echo "  created file: ${ROOT}/app/services/voice_cloning_service.py"
else
  echo "  exists file: ${ROOT}/app/services/voice_cloning_service.py (skipping)"
fi

# app/api/dependencies.py
if [ ! -e "${ROOT}/app/api/dependencies.py" ]; then
cat > "${ROOT}/app/api/dependencies.py" <<'PY'
from app.core.config import Settings
from app.services.voice_cloning_service import VoiceCloningService

def get_settings() -> Settings:
    return Settings()

def get_voice_cloning_service() -> VoiceCloningService:
    return VoiceCloningService()
PY
echo "  created file: ${ROOT}/app/api/dependencies.py"
else
  echo "  exists file: ${ROOT}/app/api/dependencies.py (skipping)"
fi

# app/api/routes.py
if [ ! -e "${ROOT}/app/api/routes.py" ]; then
cat > "${ROOT}/app/api/routes.py" <<'PY'
from fastapi import APIRouter, Depends, HTTPException
from app.models.schemas import CloneRequest, CloneResponse
from .dependencies import get_voice_cloning_service
from app.services.voice_cloning_service import VoiceCloningService

router = APIRouter()

@router.post("/clone", response_model=CloneResponse)
def clone_voice(payload: CloneRequest, svc: VoiceCloningService = Depends(get_voice_cloning_service)):
    try:
        result = svc.start_clone(payload.source_audio_url, payload.target_speaker_name or "unknown")
        return {"job_id": result["job_id"], "status": result["status"], "output_url": result.get("output")}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
PY
echo "  created file: ${ROOT}/app/api/routes.py"
else
  echo "  exists file: ${ROOT}/app/api/routes.py (skipping)"
fi

# run.py (project-level entry)
if [ ! -e "${ROOT}/run.py" ]; then
cat > "${ROOT}/run.py" <<'PY'
"""Run the FastAPI app with uvicorn (development)."""
import uvicorn
from app.core.config import Settings

settings = Settings()

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
PY
echo "  created file: ${ROOT}/run.py"
else
  echo "  exists file: ${ROOT}/run.py (skipping)"
fi

# requirements.txt
if [ ! -e "${ROOT}/requirements.txt" ]; then
cat > "${ROOT}/requirements.txt" <<'PY'
fastapi
uvicorn[standard]
pydantic
python-multipart
pytest
PY
echo "  created file: ${ROOT}/requirements.txt"
else
  echo "  exists file: ${ROOT}/requirements.txt (skipping)"
fi

# README.md
if [ ! -e "${ROOT}/README.md" ]; then
cat > "${ROOT}/README.md" <<'PY'
# voice-cloning-app

Minimal scaffold for a voice cloning microservice (FastAPI).

## Run (dev)
1. python -m venv .venv
2. source .venv/bin/activate
3. pip install -r requirements.txt
4. python run.py

## Structure
See tree in repo root.

PY
echo "  created file: ${ROOT}/README.md"
else
  echo "  exists file: ${ROOT}/README.md (skipping)"
fi

# tests/test_health.py
if [ ! -e "${ROOT}/tests/test_health.py" ]; then
cat > "${ROOT}/tests/test_health.py" <<'PY'
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
PY
echo "  created file: ${ROOT}/tests/test_health.py"
else
  echo "  exists file: ${ROOT}/tests/test_health.py (skipping)"
fi

# docker/Dockerfile
if [ ! -e "${ROOT}/docker/Dockerfile" ]; then
cat > "${ROOT}/docker/Dockerfile" <<'PY'
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
PY
echo "  created file: ${ROOT}/docker/Dockerfile"
else
  echo "  exists file: ${ROOT}/docker/Dockerfile (skipping)"
fi

# scripts/setup_venv.sh
if [ ! -e "${ROOT}/scripts/setup_venv.sh" ]; then
cat > "${ROOT}/scripts/setup_venv.sh" <<'PY'
#!/usr/bin/env bash
set -euo pipefail
python -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "Virtualenv created and dependencies installed."
PY
chmod +x "${ROOT}/scripts/setup_venv.sh"
echo "  created file: ${ROOT}/scripts/setup_venv.sh"
else
  echo "  exists file: ${ROOT}/scripts/setup_venv.sh (skipping)"
fi

# docker-compose.yml (project root)
if [ ! -e "${ROOT}/docker-compose.yml" ]; then
cat > "${ROOT}/docker-compose.yml" <<'PY'
version: "3.8"
services:
  app:
    build: ./docker
    ports:
      - "8000:8000"
    volumes:
      - ./:/app
PY
echo "  created file: ${ROOT}/docker-compose.yml"
else
  echo "  exists file: ${ROOT}/docker-compose.yml (skipping)"
fi

echo "Scaffold creation complete."

# show a small tree
echo
echo "Resulting structure (top-level):"
ls -la "${ROOT}" | sed -n '1,200p'
