# ================================
# FILE: docs/API_DOCUMENTATION.md
# ================================

# Voice Cloning API Documentation

## Overview

This API provides voice cloning and text-to-speech synthesis capabilities using state-of-the-art HuggingFace models, specifically the XTTS-v2 model from Coqui TTS.

## Features

- **Text-to-Speech Synthesis**: Convert text to natural-sounding speech
- **Voice Cloning**: Clone any voice using just a few seconds of reference audio
- **Multi-language Support**: Support for 17+ languages
- **RESTful API**: Easy integration with any frontend or application
- **File Management**: Secure upload and management of audio files

## Architecture

The application follows SOLID principles and uses several design patterns:

- **Repository Pattern**: For data access abstraction
- **Dependency Injection**: For loose coupling between components
- **Strategy Pattern**: For different TTS engines
- **Factory Pattern**: For service creation
- **Singleton Pattern**: For configuration management

## API Endpoints

### Health Check
```
GET /api/v1/health
```

### Upload Reference Audio
```
POST /api/v1/upload-audio
Content-Type: multipart/form-data

Parameters:
- file: Audio file (WAV, MP3, FLAC, etc.)
```

### Text-to-Speech Synthesis
```
POST /api/v1/synthesize
Content-Type: application/json

Body:
{
  "text": "Text to synthesize",
  "language": "en",
  "speaker_wav_path": "optional/path/to/speaker.wav",
  "speed": 1.0
}
```

### Voice Cloning
```
POST /api/v1/clone-voice
Content-Type: application/json

Body:
{
  "text": "Text to synthesize with cloned voice",
  "reference_audio_id": "uploaded_file_id",
  "language": "en"
}
```

### Download Generated Audio
```
GET /api/v1/download/{filename}
```

## Supported Languages

- English (en)
- Spanish (es)
- French (fr)
- German (de)
- Italian (it)
- Portuguese (pt)
- Polish (pl)
- Turkish (tr)
- Russian (ru)
- Dutch (nl)
- Czech (cs)
- Arabic (ar)
- Chinese (zh)
- Japanese (ja)
- Hungarian (hu)
- Korean (ko)
- Hindi (hi)

## Usage Examples

### Python Client Example

```python
import requests

# Upload reference audio
with open("reference.wav", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/v1/upload-audio",
        files={"file": f}
    )
file_id = response.json()["file_id"]

# Clone voice
response = requests.post(
    "http://localhost:8000/api/v1/clone-voice",
    json={
        "text": "Hello, this is my cloned voice!",
        "reference_audio_id": file_id,
        "language": "en"
    }
)
result = response.json()
```

### JavaScript/Node.js Example

```javascript
const FormData = require('form-data');
const fs = require('fs');

// Upload audio
const form = new FormData();
form.append('file', fs.createReadStream('reference.wav'));

fetch('http://localhost:8000/api/v1/upload-audio', {
    method: 'POST',
    body: form
})
.then(response => response.json())
.then(data => {
    // Clone voice
    return fetch('http://localhost:8000/api/v1/clone-voice', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            text: "Hello from cloned voice!",
            reference_audio_id: data.file_id,
            language: "en"
        })
    });
})
.then(response => response.json())
.then(result => console.log(result));
```

## Error Handling

The API returns structured error responses:

```json
{
  "success": false,
  "message": "Error description",
  "error_code": "ERROR_TYPE",
  "details": {}
}
```

Common error codes:
- `VALIDATION_ERROR`: Input validation failed
- `MODEL_LOAD_ERROR`: TTS model failed to load
- `AUDIO_PROCESSING_ERROR`: Audio processing failed
- `FILE_NOT_FOUND`: Requested file not found
- `INTERNAL_ERROR`: Internal server error

## Installation and Deployment

### Local Development
```bash
# Clone repository
git clone <repository_url>
cd voice-cloning-app

# Run setup script
bash scripts/setup.sh

# Start application
python run.py
```

### Docker Deployment
```bash
# Build and run with Docker Compose
bash scripts/deploy.sh
```

## Configuration

Environment variables in `.env`:

```env
APP_NAME=Voice Cloning API
DEBUG=false
USE_GPU=true
DEFAULT_MODEL=tts_models/multilingual/multi-dataset/xtts_v2
MAX_TEXT_LENGTH=1000
MAX_FILE_SIZE=10485760
```

## Performance Considerations

- GPU acceleration significantly improves synthesis speed
- Voice cloning requires 3-10 seconds of clear reference audio
- Processing time varies by text length and hardware
- Consider caching for frequently used voices

## Security

- File uploads are validated for type and size
- Temporary files are automatically cleaned up
- No persistent storage of user data by default
- Rate limiting should be implemented for production

## Limitations

- Maximum text length: 1000 characters per request
- Maximum file size: 10MB for audio uploads
- Supported audio formats: WAV, MP3, FLAC, M4A, OGG
- Reference audio should be at least 3 seconds long
- Quality depends on reference audio clarity
