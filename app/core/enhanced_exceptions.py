# ================================
# FILE: app/core/enhanced_exceptions.py
# ================================

from typing import Optional, Dict, Any, List
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ErrorCode(str, Enum):
    # Model errors
    MODEL_LOAD_ERROR = "MODEL_LOAD_ERROR"
    MODEL_INFERENCE_ERROR = "MODEL_INFERENCE_ERROR"
    GPU_MEMORY_ERROR = "GPU_MEMORY_ERROR"
    
    # Audio processing errors
    AUDIO_FORMAT_ERROR = "AUDIO_FORMAT_ERROR"
    AUDIO_TOO_SHORT = "AUDIO_TOO_SHORT"
    AUDIO_TOO_LONG = "AUDIO_TOO_LONG"
    AUDIO_QUALITY_POOR = "AUDIO_QUALITY_POOR"
    AUDIO_CORRUPTION = "AUDIO_CORRUPTION"
    
    # File handling errors
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    FILE_UPLOAD_ERROR = "FILE_UPLOAD_ERROR"
    STORAGE_FULL = "STORAGE_FULL"
    
    # Validation errors
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_PARAMETER = "MISSING_PARAMETER"
    INVALID_LANGUAGE = "INVALID_LANGUAGE"
    TEXT_TOO_LONG = "TEXT_TOO_LONG"
    
    # System errors
    SYSTEM_OVERLOAD = "SYSTEM_OVERLOAD"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"

class EnhancedException(Exception):
    """Enhanced exception with structured error information"""
    
    def __init__(self, 
                 message: str,
                 error_code: ErrorCode,
                 details: Optional[Dict[str, Any]] = None,
                 suggestions: Optional[List[str]] = None,
                 user_message: Optional[str] = None):
        
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.suggestions = suggestions or []
        self.user_message = user_message or message
        
        super().__init__(self.message)
        
        # Log the exception (do NOT include 'message' key in extra — that's reserved)
        # Use safe/unique keys in extra to avoid LogRecord collisions
        try:
            logger.error(
                f"Enhanced exception: {error_code.value} - {self.message}",
                extra={
                    "error_code": error_code.value,
                    "err_message": self.message,
                    "err_details": self.details,
                    "err_suggestions": self.suggestions,
                    "user_message": self.user_message,
                },
                exc_info=True
            )
        except Exception:
            # Fall back to a simpler log to ensure we never crash from logging
            logger.exception("Enhanced exception (fallback log): %s %s", error_code.value, self.message)

class AudioProcessingException(EnhancedException):
    """Audio processing related exceptions"""
    pass

class ModelException(EnhancedException):
    """Model loading/inference exceptions"""
    pass

class ValidationException(EnhancedException):
    """Input validation exceptions"""
    pass

class SystemException(EnhancedException):
    """System resource exceptions"""
    pass