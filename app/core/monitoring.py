# ================================
# FILE: app/core/monitoring.py
# ================================

import time
import psutil
import GPUtil
import threading
from typing import Dict, Any
from dataclasses import dataclass
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)
perf_logger = logging.getLogger("performance")

@dataclass
class SystemMetrics:
    cpu_percent: float
    memory_percent: float
    disk_usage_percent: float
    gpu_usage: float
    gpu_memory: float
    active_requests: int
    total_requests: int
    error_rate: float
    avg_response_time: float

class SystemMonitor:
    """System monitoring for production health checks"""
    
    def __init__(self):
        self.metrics = {
            'requests_total': 0,
            'requests_active': 0,
            'errors_total': 0,
            'response_times': deque(maxlen=1000),
            'start_time': time.time()
        }
        self._lock = threading.Lock()
    
    def get_system_metrics(self) -> SystemMetrics:
        """Get current system metrics"""
        try:
            # CPU and Memory
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # GPU metrics
            gpu_usage = 0
            gpu_memory = 0
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]  # First GPU
                    gpu_usage = gpu.load * 100
                    gpu_memory = gpu.memoryUtil * 100
            except:
                pass  # No GPU or GPUtil not available
            
            # Calculate error rate
            with self._lock:
                error_rate = (self.metrics['errors_total'] / max(1, self.metrics['requests_total'])) * 100
                avg_response_time = sum(self.metrics['response_times']) / max(1, len(self.metrics['response_times']))
            
            return SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                disk_usage_percent=(disk.used / disk.total) * 100,
                gpu_usage=gpu_usage,
                gpu_memory=gpu_memory,
                active_requests=self.metrics['requests_active'],
                total_requests=self.metrics['requests_total'],
                error_rate=error_rate,
                avg_response_time=avg_response_time
            )
        except Exception as e:
            logger.error(f"Failed to get system metrics: {e}")
            return SystemMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0)
    
    def record_request_start(self):
        """Record start of a request"""
        with self._lock:
            self.metrics['requests_total'] += 1
            self.metrics['requests_active'] += 1
    
    def record_request_end(self, processing_time: float, success: bool = True):
        """Record end of a request"""
        with self._lock:
            self.metrics['requests_active'] -= 1
            self.metrics['response_times'].append(processing_time)
            if not success:
                self.metrics['errors_total'] += 1
        
        # Log performance metrics
        perf_logger.info(
            "Request completed",
            extra={
                "processing_time": processing_time,
                "success": success,
                "active_requests": self.metrics['requests_active']
            }
        )

# Global monitor instance
system_monitor = SystemMonitor()