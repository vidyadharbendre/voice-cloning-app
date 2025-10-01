"""
Exception Handlers Module
Centralized exception handling for the FastAPI application
"""
import logging
import traceback
from typing import Dict, Any
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

# Import all custom exceptions
from app.core.exceptions import (
    VoiceCloningException,
    ModelLoadError,
    AudioProcessingError,
    InvalidAudioFormat,
    RateLimitExceeded,
    InsufficientResources,
    FileNotFoundError,
    ValidationError
)

logger = logging.getLogger(__name__)


async def voice_cloning_exception_handler(
    request: Request, 
    exc: VoiceCloningException
) -> JSONResponse:
    """Handle custom voice cloning exceptions"""
    logger.error(
        f"VoiceCloningException: {exc.message}",
        extra={
            "status_code": exc.status_code,
            "path": request.url.path,
            "details": exc.details
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.message,
            "status_code": exc.status_code,
            "details": exc.details,
            "path": request.url.path
        }
    )


async def http_exception_handler(
    request: Request, 
    exc: StarletteHTTPException
) -> JSONResponse:
    """Handle HTTP exceptions"""
    logger.warning(
        f"HTTP Exception: {exc.status_code} - {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "path": request.url.path
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "path": request.url.path
        }
    )


async def validation_exception_handler(
    request: Request, 
    exc: RequestValidationError
) -> JSONResponse:
    """Handle request validation errors"""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": " -> ".join(str(x) for x in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    logger.warning(
        f"Validation Error: {len(errors)} errors",
        extra={
            "path": request.url.path,
            "errors": errors
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation failed",
            "status_code": 422,
            "details": {
                "errors": errors
            },
            "path": request.url.path
        }
    )


async def general_exception_handler(
    request: Request, 
    exc: Exception
) -> JSONResponse:
    """Handle all other unhandled exceptions"""
    # Get traceback for logging
    tb = traceback.format_exc()
    
    logger.error(
        f"Unhandled Exception: {str(exc)}",
        extra={
            "path": request.url.path,
            "exception_type": type(exc).__name__,
            "traceback": tb
        },
        exc_info=True
    )
    
    # Don't expose internal errors in production
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "status_code": 500,
            "message": "An unexpected error occurred. Please try again later.",
            "path": request.url.path
        }
    )


def register_exception_handlers(app):
    """
    Register all exception handlers with the FastAPI app
    
    Args:
        app: FastAPI application instance
    """
    # Custom exceptions
    app.add_exception_handler(VoiceCloningException, voice_cloning_exception_handler)
    app.add_exception_handler(ModelLoadError, voice_cloning_exception_handler)
    app.add_exception_handler(AudioProcessingError, voice_cloning_exception_handler)
    app.add_exception_handler(InvalidAudioFormat, voice_cloning_exception_handler)
    app.add_exception_handler(RateLimitExceeded, voice_cloning_exception_handler)
    app.add_exception_handler(InsufficientResources, voice_cloning_exception_handler)
    
    # Standard exceptions
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    
    logger.info("Exception handlers registered successfully")


# Export all handlers
__all__ = [
    'register_exception_handlers',
    'voice_cloning_exception_handler',
    'http_exception_handler',
    'validation_exception_handler',
    'general_exception_handler'
]