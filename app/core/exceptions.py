"""
Custom Exceptions Module
Defines all custom exceptions used across the voice cloning application
DO NOT import from app.core.exceptions in this file!
"""
from typing import Dict, Any, Optional


class VoiceCloningException(Exception):
    """Base exception for voice cloning application"""
    def __init__(
        self, 
        message: str, 
        status_code: int = 500, 
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


# Model-related exceptions
class ModelLoadError(VoiceCloningException):
    """Raised when model loading fails"""
    def __init__(self, message: str = "Failed to load model", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=500, details=details)


class ModelNotFoundError(VoiceCloningException):
    """Raised when requested model is not found"""
    def __init__(self, message: str = "Model not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=404, details=details)


# Audio-related exceptions
class AudioProcessingError(VoiceCloningException):
    """Raised when audio processing fails"""
    def __init__(self, message: str = "Audio processing failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=400, details=details)


class InvalidAudioFormat(VoiceCloningException):
    """Raised when audio format is invalid"""
    def __init__(self, message: str = "Invalid audio format", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=400, details=details)


class AudioTooShort(VoiceCloningException):
    """Raised when audio duration is too short"""
    def __init__(self, message: str = "Audio duration too short", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=400, details=details)


class AudioTooLong(VoiceCloningException):
    """Raised when audio duration is too long"""
    def __init__(self, message: str = "Audio duration too long", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=400, details=details)


# File-related exceptions
class FileNotFoundError(VoiceCloningException):
    """Raised when file is not found"""
    def __init__(self, message: str = "File not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=404, details=details)


class FileUploadError(VoiceCloningException):
    """Raised when file upload fails"""
    def __init__(self, message: str = "File upload failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=400, details=details)


class FileSizeTooLarge(VoiceCloningException):
    """Raised when file size exceeds limit"""
    def __init__(self, message: str = "File size too large", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=413, details=details)


class InvalidFileType(VoiceCloningException):
    """Raised when file type is not supported"""
    def __init__(self, message: str = "Invalid file type", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=400, details=details)


# Validation exceptions
class ValidationError(VoiceCloningException):
    """Raised when input validation fails"""
    def __init__(self, message: str = "Validation failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=422, details=details)


class InvalidParameterError(VoiceCloningException):
    """Raised when parameter value is invalid"""
    def __init__(self, message: str = "Invalid parameter", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=400, details=details)


# Resource-related exceptions
class RateLimitExceeded(VoiceCloningException):
    """Raised when rate limit is exceeded"""
    def __init__(self, message: str = "Rate limit exceeded", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=429, details=details)


class InsufficientResources(VoiceCloningException):
    """Raised when system resources are insufficient"""
    def __init__(self, message: str = "Insufficient system resources", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=503, details=details)


class StorageError(VoiceCloningException):
    """Raised when storage operation fails"""
    def __init__(self, message: str = "Storage operation failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=500, details=details)


# Authentication and authorization exceptions
class AuthenticationError(VoiceCloningException):
    """Raised when authentication fails"""
    def __init__(self, message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=401, details=details)


class AuthorizationError(VoiceCloningException):
    """Raised when authorization fails"""
    def __init__(self, message: str = "Not authorized", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=403, details=details)


# Service-related exceptions
class ServiceUnavailable(VoiceCloningException):
    """Raised when service is unavailable"""
    def __init__(self, message: str = "Service unavailable", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=503, details=details)


class TimeoutError(VoiceCloningException):
    """Raised when operation times out"""
    def __init__(self, message: str = "Operation timed out", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=408, details=details)


class ConfigurationError(VoiceCloningException):
    """Raised when configuration is invalid"""
    def __init__(self, message: str = "Configuration error", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=500, details=details)