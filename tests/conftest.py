# ================================
# FILE: tests/conftest.py
# ================================

import pytest
import asyncio
import os
import tempfile
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

@pytest.fixture
def client():
    """Test client fixture"""
    return TestClient(app)

@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def temp_audio_file():
    """Create a temporary audio file for testing"""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        # Create a simple sine wave for testing
        import numpy as np
        import soundfile as sf
        
        duration = 5.0  # seconds
        sample_rate = 22050
        frequency = 440.0  # Hz
        
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio_data = np.sin(frequency * 2 * np.pi * t)
        
        sf.write(f.name, audio_data, sample_rate)
        yield f.name
    
    # Cleanup
    if os.path.exists(f.name):
        os.unlink(f.name)