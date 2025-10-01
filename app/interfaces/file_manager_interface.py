# ================================
# FILE: app/interfaces/file_manager_interface.py
# ================================

from abc import ABC, abstractmethod
from typing import Optional
from fastapi import UploadFile

class IFileManager(ABC):
    """Interface for file management operations"""
    
    @abstractmethod
    async def save_upload(self, file: UploadFile) -> str:
        """Save uploaded file and return file ID"""
        pass
    
    @abstractmethod
    async def get_file_path(self, file_id: str) -> Optional[str]:
        """Get file path by ID"""
        pass
    
    @abstractmethod
    async def delete_file(self, file_id: str) -> bool:
        """Delete file by ID"""
        pass
    
    @abstractmethod
    async def cleanup_old_files(self, max_age_hours: int = 24) -> int:
        """Clean up old files and return number of deleted files"""
        pass