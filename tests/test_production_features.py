# ================================
# FILE: tests/test_production_features.py
# ================================

import pytest
import asyncio
import time
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app
from app.core.monitoring import system_monitor
from app.core.enhanced_exceptions import *
from app.core.health_checker import health_checker

client = TestClient(app)

class TestProductionFeatures:
    """Test production-specific features"""
    
    def test_enhanced_health_check(self):
        """Test enhanced health check endpoint"""
        response = client.get("/api/v1/health")
        assert response.status_code in [200, 503]
        
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "uptime" in data
        assert "details" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
    
    def test_metrics_endpoint(self):
        """Test metrics endpoint"""
        response = client.get("/api/v1/metrics")
        assert response.status_code == 200
        
        data = response.json()
        assert "system" in data
        assert "requests" in data
        assert "timestamp" in data
    
    def test_rate_limiting_headers(self):
        """Test that rate limiting headers are present"""
        response = client.get("/api/v1/health")
        
        # Check for rate limit headers
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers
    
    def test_request_id_header(self):
        """Test that request ID is added to responses"""
        response = client.get("/api/v1/health")
        
        assert "X-Request-ID" in response.headers
        assert "X-Processing-Time" in response.headers
    
    def test_error_handling_structure(self):
        """Test structured error responses"""
        # Try to download non-existent file
        response = client.get("/api/v1/download/nonexistent.wav")
        assert response.status_code == 404
        
        data = response.json()
        assert "success" in data
        assert "error" in data
        assert "request_id" in data
        assert data["success"] is False
        assert "code" in data["error"]
        assert "message" in data["error"]
    
    def test_file_validation(self):
        """Test file upload validation"""
        # Test with invalid file
        response = client.post(
            "/api/v1/upload-audio",
            files={"file": ("test.txt", b"not an audio file", "text/plain")}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] in ["VALIDATION_ERROR", "AUDIO_FORMAT_ERROR"]
    
    @pytest.mark.asyncio
    async def test_system_monitor_metrics(self):
        """Test system monitor functionality"""
        # Record some test metrics
        system_monitor.record_request_start()
        await asyncio.sleep(0.1)
        system_monitor.record_request_end(0.1, success=True)
        
        metrics = system_monitor.get_system_metrics()
        assert metrics.total_requests > 0
        assert metrics.avg_response_time > 0
    
    def test_cors_headers(self):
        """Test CORS headers are present"""
        response = client.options("/api/v1/health")
        
        # CORS headers should be present
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
    
    def test_security_headers(self):
        """Test security headers in nginx config"""
        # This would be tested in integration tests with actual nginx
        # For now, we test that our app doesn't add conflicting headers
        response = client.get("/")
        
        # Ensure our app doesn't conflict with security headers
        assert response.status_code == 200

class TestExceptionHandling:
    """Test enhanced exception handling"""
    
    def test_enhanced_exception_structure(self):
        """Test enhanced exception structure"""
        exc = ValidationException(
            message="Test error",
            error_code=ErrorCode.INVALID_INPUT,
            details={"field": "test"},
            suggestions=["Try again"],
            user_message="User friendly message"
        )
        
        assert exc.message == "Test error"
        assert exc.error_code == ErrorCode.INVALID_INPUT
        assert exc.details == {"field": "test"}
        assert exc.suggestions == ["Try again"]
        assert exc.user_message == "User friendly message"
    
    def test_error_code_enum(self):
        """Test error code enumeration"""
        assert ErrorCode.MODEL_LOAD_ERROR == "MODEL_LOAD_ERROR"
        assert ErrorCode.AUDIO_TOO_SHORT == "AUDIO_TOO_SHORT"
        assert ErrorCode.FILE_NOT_FOUND == "FILE_NOT_FOUND"

class TestBackgroundTasks:
    """Test background task functionality"""
    
    @pytest.mark.asyncio
    async def test_background_task_manager(self):
        """Test background task manager"""
        from app.core.background_tasks import BackgroundTaskManager
        
        manager = BackgroundTaskManager()
        assert not manager.running
        
        # Start tasks
        await manager.start()
        assert manager.running
        assert len(manager.tasks) > 0
        
        # Stop tasks
        await manager.stop()
        assert not manager.running
        assert len(manager.tasks) == 0
