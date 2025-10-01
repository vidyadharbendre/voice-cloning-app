# ================================
# FILE: app/core/rate_limiting.py
# ================================

import time
import asyncio
from collections import defaultdict, deque
from typing import Dict, Optional
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """Token bucket rate limiter for API endpoints"""
    
    def __init__(self):
        self.buckets: Dict[str, dict] = defaultdict(lambda: {
            'tokens': 0,
            'last_update': time.time(),
            'requests': deque(maxlen=100)
        })
        self.limits = {
            'upload': {'requests': 10, 'window': 3600},      # 10 uploads per hour
            'synthesize': {'requests': 100, 'window': 3600},  # 100 synthesis per hour
            'clone': {'requests': 50, 'window': 3600},        # 50 clones per hour
            'default': {'requests': 200, 'window': 3600}      # 200 requests per hour
        }
    
    async def check_rate_limit(self, 
                             client_id: str, 
                             endpoint: str = 'default', 
                             cost: int = 1) -> bool:
        """Check if request is within rate limits"""
        
        try:
            limit_config = self.limits.get(endpoint, self.limits['default'])
            bucket = self.buckets[f"{client_id}:{endpoint}"]
            current_time = time.time()
            
            # Clean old requests
            window_start = current_time - limit_config['window']
            while bucket['requests'] and bucket['requests'][0] < window_start:
                bucket['requests'].popleft()
            
            # Check if within limits
            if len(bucket['requests']) + cost <= limit_config['requests']:
                # Add current request(s)
                for _ in range(cost):
                    bucket['requests'].append(current_time)
                return True
            else:
                # Rate limit exceeded
                logger.warning(
                    f"Rate limit exceeded for {client_id} on {endpoint}",
                    extra={
                        "client_id": client_id,
                        "endpoint": endpoint,
                        "current_requests": len(bucket['requests']),
                        "limit": limit_config['requests']
                    }
                )
                return False
                
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            return True  # Allow request on rate limiter error

    def get_rate_limit_info(self, client_id: str, endpoint: str = 'default') -> dict:
        """Get current rate limit status"""
        limit_config = self.limits.get(endpoint, self.limits['default'])
        bucket = self.buckets[f"{client_id}:{endpoint}"]
        current_time = time.time()
        
        # Clean old requests
        window_start = current_time - limit_config['window']
        while bucket['requests'] and bucket['requests'][0] < window_start:
            bucket['requests'].popleft()
        
        remaining = limit_config['requests'] - len(bucket['requests'])
        reset_time = int(current_time + limit_config['window'])
        
        return {
            'limit': limit_config['requests'],
            'remaining': max(0, remaining),
            'reset': reset_time,
            'window': limit_config['window']
        }

# Global rate limiter
rate_limiter = RateLimiter()
