# ================================
# FILE: tests/test_api.py
# ================================

import pytest
from fastapi.testclient import TestClient
import json

def test_health_check(client: TestClient):
    """Test health check endpoint"""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data

def test_root_endpoint(client: TestClient):
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data

def test_upload_audio(client: TestClient, temp_audio_file):
    """Test audio upload endpoint"""
    with open(temp_audio_file, "rb") as f:
        response = client.post(
            "/api/v1/upload-audio",
            files={"file": ("test.wav", f, "audio/wav")}
        )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "file_id" in data

def test_synthesize_speech(client: TestClient):
    """Test speech synthesis endpoint"""
    request_data = {
        "text": "Hello, this is a test message.",
        "language": "en"
    }
    
    response = client.post("/api/v1/synthesize", json=request_data)
    assert response.status_code == 200
    # Note: Actual synthesis might fail without proper model setup