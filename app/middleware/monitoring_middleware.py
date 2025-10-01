# ================================
# FILE: app/middleware/monitoring_middleware.py
# ================================

import time
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import logging
from app.core.monitoring import system_monitor

logger = logging.getLogger(__name__)

class MonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware for request monitoring and logging"""
    
    async def dispatch(self, request: Request, call_next):
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Log request start
        start_time = time.time()
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={"request_id": request_id, "method": request.method, "path": request.url.path}
        )
        
        # Record metrics
        system_monitor.record_request_start()
        
        try:
            # Process request
            response = await call_next(request)
            success = response.status_code < 400
            
        except Exception as e:
            success = False
            logger.error(
                f"Request failed: {str(e)}",
                extra={"request_id": request_id},
                exc_info=True
            )
            # Return error response
            response = Response(
                content=f'{{"error": "Internal server error", "request_id": "{request_id}"}}',
                status_code=500,
                media_type="application/json"
            )
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Log request completion
        logger.info(
            f"Request completed: {request.method} {request.url.path} - {response.status_code}",
            extra={
                "request_id": request_id,
                "status_code": response.status_code,
                "processing_time": processing_time
            }
        )
        
        # Record metrics
        system_monitor.record_request_end(processing_time, success)
        
        # Add response headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Processing-Time"] = str(processing_time)
        
        return response
