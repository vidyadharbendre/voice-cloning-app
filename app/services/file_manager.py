# ================================
# FILE: app/services/file_manager.py
# ================================

import os
import uuid
import time
import aiofiles
from typing import Optional
from fastapi import UploadFile
from app.interfaces.file_manager_interface import IFileManager
from app.core.config import settings
from app.core.exceptions import FileNotFoundError, ValidationError

class FileManager(IFileManager):
    """File management service following Single Responsibility Principle"""
    
    def __init__(self):
        self.upload_dir = settings.upload_dir
        self.output_dir = settings.output_dir
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure required directories exist"""
        os.makedirs(self.upload_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
    
    async def save_upload(self, file: UploadFile) -> str:
        """Save uploaded file and return file ID"""
        try:
            # Validate file
            await self._validate_upload(file)
            
            # Generate unique file ID
            file_id = str(uuid.uuid4())
            file_extension = os.path.splitext(file.filename)[1].lower()
            file_path = os.path.join(self.upload_dir, f"{file_id}{file_extension}")
            
            # Save file
            async with aiofiles.open(file_path, 'wb') as f:
                content = await file.read()
                await f.write(content)
            
            return file_id
        except Exception as e:
            raise ValidationError(f"Failed to save uploaded file: {str(e)}")
    
    async def get_file_path(self, file_id: str) -> Optional[str]:
        """Get file path by ID"""
        # Look for file with any allowed extension
        for ext in settings.allowed_audio_formats:
            file_path = os.path.join(self.upload_dir, f"{file_id}{ext}")
            if os.path.exists(file_path):
                return file_path
        return None
    
    async def delete_file(self, file_id: str) -> bool:
        """Delete file by ID"""
        try:
            file_path = await self.get_file_path(file_id)
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception:
            return False
    
    async def cleanup_old_files(self, max_age_hours: int = 24) -> int:
        """Clean up old files and return number of deleted files"""
        deleted_count = 0
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        for directory in [self.upload_dir, self.output_dir]:
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                if os.path.isfile(file_path):
                    file_age = current_time - os.path.getmtime(file_path)
                    if file_age > max_age_seconds:
                        try:
                            os.remove(file_path)
                            deleted_count += 1
                        except Exception:
                            pass
        
        return deleted_count
    
    async def _validate_upload(self, file: UploadFile) -> None:
        """Validate uploaded file"""
        if not file.filename:
            raise ValidationError("No filename provided")
        
        # Check file extension
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in settings.allowed_audio_formats:
            raise ValidationError(f"Unsupported file format. Allowed: {', '.join(settings.allowed_audio_formats)}")
        
        # Check file size (we need to read to check size, then reset)
        content = await file.read()
        if len(content) > settings.max_file_size:
            raise ValidationError(f"File too large. Maximum size: {settings.max_file_size // (1024*1024)}MB")
        
        # Reset file position
        await file.seek(0)