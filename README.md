# ================================
# FILE: README.md
# ================================

# Voice Cloning Application 🎤

A production-ready voice cloning and text-to-speech application built with FastAPI and HuggingFace's state-of-the-art XTTS-v2 model. This application provides ElevenLabs-like functionality as a free, open-source alternative.

## ✨ Features

- 🎯 **Voice Cloning**: Clone any voice with just 3-10 seconds of reference audio
- 🌍 **Multi-language Support**: 17+ languages supported
- 🚀 **High-Quality Synthesis**: Uses Coqui's XTTS-v2 model for natural-sounding speech
- 🏗️ **Clean Architecture**: Follows SOLID principles and design patterns
- 🔌 **RESTful API**: Easy integration with any frontend
- 🐳 **Docker Ready**: Complete containerization setup
- 🧪 **Comprehensive Tests**: Full test suite included
- 📚 **Complete Documentation**: API docs and development guides

## 🚀 Quick Start

### Option 1: Local Development

```bash
# Clone the repository
git clone <your-repo-url>
cd voice-cloning-app

# Run setup script
bash scripts/setup.sh

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Start the application
python run.py
```

### Option 2: Docker Deployment

```bash
# Quick deployment
bash scripts/deploy.sh

# Or manually with docker-compose
docker-compose -f docker/docker-compose.yml up -d
```

## 📖 Usage

### 1. Health Check
```bash
curl http://localhost:8000/api/v1/health
```

### 2. Upload Reference Audio
```bash
curl -X POST \
  http://localhost:8000/api/v1/upload-audio \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@reference_voice.wav'
```

### 3. Clone Voice
```bash
curl -X POST \
  http://localhost:8000/api/v1/clone-voice \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "Hello! This is my cloned voice speaking.",
    "reference_audio_id": "your_uploaded_file_id",
    "language": "en"
  }'
```

### 4. Text-to-Speech (without cloning)
```bash
curl -X POST \
  http://localhost:8000/api/v1/synthesize \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "Hello! This is synthesized speech.",
    "language": "en"
  }'
```

## 🏗️ Architecture

This application is built with clean architecture principles:

```
┌─────────────────┐
│   FastAPI App   │  ← API Layer
├─────────────────┤
│    Services     │  ← Business Logic
├─────────────────┤
│   Interfaces    │  ← Abstractions
├─────────────────┤
│ Implementations │  ← Concrete Classes
└─────────────────┘
```

### Design Patterns Used:
- **Repository Pattern**: Data access abstraction
- **Dependency Injection**: Loose coupling
- **Strategy Pattern**: Pluggable TTS engines
- **Factory Pattern**: Service creation
- **Singleton Pattern**: Configuration management

### SOLID Principles:
- ✅ **Single Responsibility**: Each class has one reason to change
- ✅ **Open/Closed**: Open for extension, closed for modification
- ✅ **Liskov Substitution**: Implementations are interchangeable
- ✅ **Interface Segregation**: Focused, minimal interfaces
- ✅ **Dependency Inversion**: Depend on abstractions, not concretions

## 🌍 Supported Languages

- 🇺🇸 English (en)
- 🇪🇸 Spanish (es)
- 🇫🇷 French (fr)
- 🇩🇪 German (de)
- 🇮🇹 Italian (it)
- 🇵🇹 Portuguese (pt)
- 🇵🇱 Polish (pl)
- 🇹🇷 Turkish (tr)
- 🇷🇺 Russian (ru)
- 🇳🇱 Dutch (nl)
- 🇨🇿 Czech (cs)
- 🇸🇦 Arabic (ar)
- 🇨🇳 Chinese (zh)
- 🇯🇵 Japanese (ja)
- 🇭🇺 Hungarian (hu)
- 🇰🇷 Korean (ko)
- 🇮🇳 Hindi (hi)

## 📊 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/upload-audio` | POST | Upload reference audio |
| `/api/v1/synthesize` | POST | Text-to-speech synthesis |
| `/api/v1/clone-voice` | POST | Voice cloning |
| `/api/v1/download/{filename}` | GET | Download generated audio |
| `/docs` | GET | Interactive API documentation |

## 🛠️ Configuration

Environment variables in `.env`:

```env
# Application
APP_NAME=Voice Cloning API
DEBUG=false
USE_GPU=true

# Model
DEFAULT_MODEL=tts_models/multilingual/multi-dataset/xtts_v2
MAX_TEXT_LENGTH=1000

# Files
MAX_FILE_SIZE=10485760  # 10MB
UPLOAD_DIR=uploads
OUTPUT_DIR=outputs

# Audio
SAMPLE_RATE=22050
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_api.py
```

## 📈 Performance

### GPU Acceleration
- Automatic CUDA detection
- 5-10x faster synthesis with GPU
- Fallback to CPU if GPU unavailable

### Optimization Tips
- Use GPU for production deployment
- Clear reference audio (3-10 seconds optimal)
- Batch requests for better throughput
- Monitor memory usage for long texts

## 🔒 Security Features

- ✅ File type validation
- ✅ File size limits
- ✅ Input sanitization
- ✅ Automatic file cleanup
- ✅ CORS configuration
- ✅ Error handling without data leakage

## 🚀 Deployment Options

### Development
```bash
python run.py
# Access at http://localhost:8000
```

### Production with Docker
```bash
docker-compose up -d
# Includes health checks and restart policies
```

### Cloud Deployment
- AWS ECS/Fargate ready
- Google Cloud Run compatible
- Azure Container Instances ready
- Kubernetes manifests available in `/k8s` (can be added)

## 📋 Requirements

### Minimum System Requirements
- Python 3.10+
- 4GB RAM (8GB+ recommended)
- 2GB disk space for models
- CPU: 2+ cores

### Recommended for Production
- GPU with 4GB+ VRAM (RTX 3060 or better)
- 16GB+ RAM
- SSD storage
- Load balancer for multiple instances

## 🔧 Troubleshooting

### Common Issues

**Model Loading Fails**
```bash
# Clear cache and retry
rm -rf ~/.cache/tts
pip install --upgrade TTS
```

**GPU Not Detected**
```bash
# Check CUDA installation
python -c "import torch; print(torch.cuda.is_available())"

# Install CUDA-compatible PyTorch
pip install torch==2.1.0+cu118 --index-url https://download.pytorch.org/whl/cu118
```

**File Upload Issues**
- Check file format (WAV, MP3, FLAC supported)
- Ensure file size < 10MB
- Verify audio quality (clear speech, minimal noise)

**Performance Issues**
- Enable GPU acceleration
- Reduce batch size for limited memory
- Use shorter reference audio (3-10 seconds optimal)

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. **Make your changes** following our coding standards
4. **Add tests** for new functionality
5. **Run the test suite**
   ```bash
   pytest tests/
   ```
6. **Update documentation** if needed
7. **Submit a pull request**

### Development Guidelines
- Follow SOLID principles
- Use appropriate design patterns
- Add comprehensive tests
- Update documentation
- Use type hints
- Follow PEP 8 style guide

## 📚 Documentation

- **[API Documentation](docs/API_DOCUMENTATION.md)**: Complete API reference
- **[Development Guide](docs/DEVELOPMENT.md)**: Architecture and development setup
- **[Jupyter Demo](notebooks/voice_cloning_demo.ipynb)**: Interactive examples
- **[Auto-generated Docs](http://localhost:8000/docs)**: Swagger UI when running

## 🎯 Roadmap

### Current Features ✅
- [x] Voice cloning with XTTS-v2
- [x] Multi-language TTS
- [x] RESTful API
- [x] Docker support
- [x] Comprehensive documentation
- [x] Test suite

### Upcoming Features 🚧
- [ ] Voice similarity scoring
- [ ] Batch processing API
- [ ] WebSocket real-time synthesis
- [ ] Voice library management
- [ ] Audio quality enhancement
- [ ] Multiple TTS model support
- [ ] Web UI frontend
- [ ] Voice emotion control
- [ ] API rate limiting
- [ ] Caching layer with Redis

### Future Enhancements 🔮
- [ ] Custom model fine-tuning
- [ ] Voice morphing capabilities
- [ ] Real-time voice conversion
- [ ] Voice activity detection
- [ ] Speaker diarization
- [ ] Multi-speaker synthesis
- [ ] SSML support
- [ ] Pronunciation control

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Coqui TTS Team**: For the amazing XTTS-v2 model
- **HuggingFace**: For the transformers library ecosystem
- **FastAPI**: For the excellent web framework
- **Contributors**: Everyone who helps improve this project

## 📞 Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/your-repo/issues)
- **Discussions**: [Community discussions](https://github.com/your-repo/discussions)
- **Documentation**: [Full documentation](docs/)

## ⚡ Quick Examples

### Python Client
```python
import requests
import json

# Health check
response = requests.get("http://localhost:8000/api/v1/health")
print(json.dumps(response.json(), indent=2))

# Upload and clone voice
with open("voice_sample.wav", "rb") as f:
    upload_response = requests.post(
        "http://localhost:8000/api/v1/upload-audio",
        files={"file": f}
    )

file_id = upload_response.json()["file_id"]

clone_response = requests.post(
    "http://localhost:8000/api/v1/clone-voice",
    json={
        "text": "This is my cloned voice!",
        "reference_audio_id": file_id,
        "language": "en"
    }
)

print(clone_response.json())
```

### JavaScript/Node.js
```javascript
const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');

async function cloneVoice() {
    // Upload reference audio
    const form = new FormData();
    form.append('file', fs.createReadStream('voice_sample.wav'));
    
    const uploadResponse = await axios.post(
        'http://localhost:8000/api/v1/upload-audio',
        form,
        { headers: form.getHeaders() }
    );
    
    const fileId = uploadResponse.data.file_id;
    
    // Clone voice
    const cloneResponse = await axios.post(
        'http://localhost:8000/api/v1/clone-voice',
        {
            text: "Hello from my cloned voice!",
            reference_audio_id: fileId,
            language: "en"
        }
    );
    
    console.log(cloneResponse.data);
}

cloneVoice();
```

### cURL Examples
```bash
# Health check
curl -X GET http://localhost:8000/api/v1/health

# Upload audio
curl -X POST \
  http://localhost:8000/api/v1/upload-audio \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@voice_sample.wav'

# Clone voice
curl -X POST \
  http://localhost:8000/api/v1/clone-voice \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "Amazing voice cloning!",
    "reference_audio_id": "your-file-id-here",
    "language": "en"
  }'
```

## 🎨 Frontend Integration

This API is designed to work with any frontend framework:

### React Example
```jsx
import React, { useState } from 'react';
import axios from 'axios';

function VoiceCloner() {
    const [audioFile, setAudioFile] = useState(null);
    const [text, setText] = useState('');
    const [result, setResult] = useState(null);

    const handleCloneVoice = async () => {
        // Upload audio
        const formData = new FormData();
        formData.append('file', audioFile);
        
        const uploadResponse = await axios.post(
            '/api/v1/upload-audio',
            formData
        );
        
        // Clone voice
        const cloneResponse = await axios.post('/api/v1/clone-voice', {
            text: text,
            reference_audio_id: uploadResponse.data.file_id,
            language: 'en'
        });
        
        setResult(cloneResponse.data);
    };

    return (
        <div>
            <input 
                type="file" 
                accept="audio/*" 
                onChange={(e) => setAudioFile(e.target.files[0])} 
            />
            <textarea 
                value={text} 
                onChange={(e) => setText(e.target.value)}
                placeholder="Enter text to synthesize..."
            />
            <button onClick={handleCloneVoice}>Clone Voice</button>
            {result && (
                <audio controls src={`/api/v1/download/${result.audio_file_path}`} />
            )}
        </div>
    );
}

export default VoiceCloner;
```

---

**🎤 Start cloning voices like a pro! 🚀**

For detailed setup instructions, see our [Development Guide](docs/DEVELOPMENT.md).
For API details, check our [API Documentation](docs/API_DOCUMENTATION.md).