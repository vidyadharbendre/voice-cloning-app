#================================
# FILE: tests/test_services.py
# ================================

import pytest
import tempfile
import os
from app.services.audio_processor import AudioProcessor
from app.services.file_manager import FileManager
from fastapi import UploadFile
import io

@pytest.mark.asyncio
async def test_audio_processor_validation():
    """Test audio processor validation"""
    processor = AudioProcessor()
    
    # Test with non-existent file
    result = await processor.validate_audio("nonexistent.wav")
    assert result is False

@pytest.mark.asyncio
async def test_file_manager():
    """Test file manager functionality"""
    manager = FileManager()
    
    # Create a mock upload file
    content = b"fake audio content"
    upload_file = UploadFile(
        filename="test.wav",
        file=io.BytesIO(content)
    )
    
    # Test file operations
    file_id = await manager.save_upload(upload_file)
    assert file_id is not None
    
    file_path = await manager.get_file_path(file_id)
    assert file_path is not None
    assert os.path.exists(file_path)
    
    # Cleanup
    deleted = await manager.delete_file(file_id)
    assert deleted is True
