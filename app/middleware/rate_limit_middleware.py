# ================================
# FILE: app/middleware/rate_limit_middleware.py
# ================================

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.rate_limiting import rate_limiter

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for API rate limiting"""
    
    def get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting"""
        # Use API key if provided, otherwise use IP
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"api:{api_key}"
        
        # Get IP address (handle proxies)
        client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if not client_ip:
            client_ip = request.headers.get("X-Real-IP", "")
        if not client_ip:
            client_ip = request.client.host if request.client else "unknown"
        
        return f"ip:{client_ip}"
    
    def get_endpoint_type(self, path: str) -> str:
        """Determine endpoint type for rate limiting"""
        if "upload" in path:
            return "upload"
        elif "synthesize" in path:
            return "synthesize"
        elif "clone" in path:
            return "clone"
        return "default"
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/api/v1/health"]:
            return await call_next(request)
        
        client_id = self.get_client_id(request)
        endpoint_type = self.get_endpoint_type(request.url.path)
        
        # Check rate limit
        allowed = await rate_limiter.check_rate_limit(client_id, endpoint_type)
        
        if not allowed:
            # Get rate limit info for headers
            rate_info = rate_limiter.get_rate_limit_info(client_id, endpoint_type)
            
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "limit": rate_info['limit'],
                    "window": rate_info['window'],
                    "reset": rate_info['reset']
                },
                headers={
                    "X-RateLimit-Limit": str(rate_info['limit']),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(rate_info['reset'])
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        rate_info = rate_limiter.get_rate_limit_info(client_id, endpoint_type)
        response.headers["X-RateLimit-Limit"] = str(rate_info['limit'])
        response.headers["X-RateLimit-Remaining"] = str(rate_info['remaining'])
        response.headers["X-RateLimit-Reset"] = str(rate_info['reset'])
        
        return response