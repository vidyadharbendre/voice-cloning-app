"""
Production-Ready Logging Configuration Module
Handles application-wide logging with structured JSON logging, rotation, and performance tracking
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
import json
import traceback
from datetime import datetime
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields
        if hasattr(record, 'user_id'):
            log_entry["user_id"] = record.user_id
        if hasattr(record, 'request_id'):
            log_entry["request_id"] = record.request_id
        if hasattr(record, 'processing_time'):
            log_entry["processing_time"] = record.processing_time
        if hasattr(record, 'endpoint'):
            log_entry["endpoint"] = record.endpoint
        if hasattr(record, 'status_code'):
            log_entry["status_code"] = record.status_code
            
        return json.dumps(log_entry)


class ColoredConsoleFormatter(logging.Formatter):
    """Colored formatter for better console readability"""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # Format the message
        formatted_msg = super().format(record)
        
        # Add color to level name
        formatted_msg = formatted_msg.replace(
            record.levelname,
            f"{color}{record.levelname}{reset}"
        )
        
        return formatted_msg


def setup_logging(
    log_level: str = "INFO",
    log_dir: str = "logs",
    enable_json: bool = True,
    enable_colors: bool = True
):
    """
    Configure structured logging for production with multiple handlers
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory to store log files
        enable_json: Enable JSON formatting for file logs
        enable_colors: Enable colored output for console logs
    """
    
    # Create logs directory
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove default handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler with optional colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    if enable_colors and sys.stdout.isatty():
        console_formatter = ColoredConsoleFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Choose formatter based on configuration
    file_formatter = JSONFormatter() if enable_json else logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # General application log handler
    app_handler = RotatingFileHandler(
        log_path / "app.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(file_formatter)
    root_logger.addHandler(app_handler)
    
    # Error log handler (errors and critical only)
    error_handler = RotatingFileHandler(
        log_path / "error.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    root_logger.addHandler(error_handler)
    
    # Performance log handler
    perf_handler = RotatingFileHandler(
        log_path / "performance.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=3,
        encoding='utf-8'
    )
    perf_handler.setLevel(logging.INFO)
    perf_handler.setFormatter(file_formatter)
    
    perf_logger = logging.getLogger("performance")
    perf_logger.addHandler(perf_handler)
    perf_logger.setLevel(logging.INFO)
    perf_logger.propagate = False  # Don't propagate to root logger
    
    # Security log handler
    security_handler = RotatingFileHandler(
        log_path / "security.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    security_handler.setLevel(logging.INFO)
    security_handler.setFormatter(file_formatter)
    
    security_logger = logging.getLogger("security")
    security_logger.addHandler(security_handler)
    security_logger.setLevel(logging.INFO)
    security_logger.propagate = False
    
    # Suppress noisy third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    root_logger.info(
        f"Logging initialized - Level: {log_level}, Directory: {log_dir}, "
        f"JSON: {enable_json}, Colors: {enable_colors}"
    )
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def log_performance(
    logger_name: str,
    operation: str,
    duration: float,
    user_id: Optional[str] = None,
    request_id: Optional[str] = None,
    **kwargs
):
    """
    Log performance metrics
    
    Args:
        logger_name: Name of the logger
        operation: Operation being logged
        duration: Duration in seconds
        user_id: Optional user identifier
        request_id: Optional request identifier
        **kwargs: Additional metadata
    """
    perf_logger = logging.getLogger("performance")
    
    extra = {
        "operation": operation,
        "processing_time": duration,
    }
    
    if user_id:
        extra["user_id"] = user_id
    if request_id:
        extra["request_id"] = request_id
    
    extra.update(kwargs)
    
    perf_logger.info(
        f"{operation} completed in {duration:.3f}s",
        extra=extra
    )


def log_security_event(
    event_type: str,
    message: str,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    severity: str = "INFO",
    **kwargs
):
    """
    Log security-related events
    
    Args:
        event_type: Type of security event (e.g., 'auth_failure', 'rate_limit')
        message: Event description
        user_id: Optional user identifier
        ip_address: Optional IP address
        severity: Log level (INFO, WARNING, ERROR)
        **kwargs: Additional metadata
    """
    security_logger = logging.getLogger("security")
    
    extra = {
        "event_type": event_type,
    }
    
    if user_id:
        extra["user_id"] = user_id
    if ip_address:
        extra["ip_address"] = ip_address
    
    extra.update(kwargs)
    
    log_method = getattr(security_logger, severity.lower())
    log_method(message, extra=extra)
# Initialize logging on module import
logger = setup_logging()    
# Example usage:
# logger = get_logger(__name__)
# logger.info("Application started")
# log_performance("database_query", 0.123, user_id="user123", request_id="req456")
# log_security_event("auth_failure", "Invalid login attempt", user_id="user123", ip_address="192.168.1.1")