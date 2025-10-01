# app/status.py
"""
Shared runtime status object used by health checks and monitoring.
Minimal and safe to import at application startup.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Status:
    start_time: float = field(default_factory=time.time)
    model_loaded: bool = False
    last_model_check: Optional[float] = None
    total_requests: int = 0
    active_requests: int = 0
    error_rate: float = 0.0

    @property
    def service_uptime(self) -> float:
        return time.time() - self.start_time

# singleton instance
status = Status()
