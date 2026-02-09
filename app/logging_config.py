"""
Structured logging configuration for the Persian Transcription API.

This module provides JSON-formatted logging with context information
for debugging and monitoring purposes.
"""

import logging
import sys
from typing import Optional
from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """
    Custom JSON formatter that adds standard fields to all log records.
    
    This formatter ensures consistent structure across all log messages,
    including timestamp, level, logger name, message, and any additional
    context fields.
    """
    
    def add_fields(self, log_record, record, message_dict):
        """
        Add custom fields to the log record.
        
        Args:
            log_record: The dictionary that will be logged as JSON
            record: The LogRecord instance
            message_dict: Dictionary of message fields
        """
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        
        # Add standard fields
        log_record['timestamp'] = self.formatTime(record, self.datefmt)
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['module'] = record.module
        log_record['function'] = record.funcName
        log_record['line'] = record.lineno
        
        # Add exception info if present
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)
        
        # Add stack trace if present
        if record.stack_info:
            log_record['stack_trace'] = self.formatStack(record.stack_info)


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    use_json: bool = True
) -> None:
    """
    Configure structured logging for the application.
    
    This function sets up logging with JSON formatting for structured logs
    that include context information like job_id, file info, and stack traces.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path to write logs to (in addition to stdout)
        use_json: Whether to use JSON formatting (default: True)
    
    Example:
        >>> setup_logging(log_level="INFO", use_json=True)
        >>> logger = logging.getLogger(__name__)
        >>> logger.info("Application started", extra={"version": "1.0.0"})
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers
    root_logger.handlers = []
    
    # Create formatter
    if use_json:
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(logger)s %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Log initial message
    root_logger.info(
        "Logging configured",
        extra={
            "log_level": log_level,
            "use_json": use_json,
            "log_file": log_file
        }
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.
    
    Args:
        name: Logger name (typically __name__ of the module)
    
    Returns:
        Logger instance
    
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing request", extra={"job_id": "123"})
    """
    return logging.getLogger(name)


def log_with_context(
    logger: logging.Logger,
    level: str,
    message: str,
    job_id: Optional[str] = None,
    file_path: Optional[str] = None,
    file_size: Optional[int] = None,
    error: Optional[Exception] = None,
    **kwargs
) -> None:
    """
    Log a message with structured context information.
    
    This helper function makes it easy to log messages with consistent
    context fields like job_id, file information, and error details.
    
    Args:
        logger: Logger instance to use
        level: Log level (debug, info, warning, error, critical)
        message: Log message
        job_id: Optional job identifier
        file_path: Optional file path
        file_size: Optional file size in bytes
        error: Optional exception instance
        **kwargs: Additional context fields
    
    Example:
        >>> logger = get_logger(__name__)
        >>> log_with_context(
        ...     logger,
        ...     "info",
        ...     "Processing audio file",
        ...     job_id="550e8400-e29b-41d4-a716-446655440000",
        ...     file_path="/tmp/audio.wav",
        ...     file_size=1024000
        ... )
    """
    # Build context dictionary
    context = {}
    
    if job_id:
        context['job_id'] = job_id
    
    if file_path:
        context['file_path'] = file_path
    
    if file_size is not None:
        context['file_size'] = file_size
    
    if error:
        context['error_type'] = type(error).__name__
        context['error_message'] = str(error)
    
    # Add any additional context
    context.update(kwargs)
    
    # Get log method
    log_method = getattr(logger, level.lower())
    
    # Log with context
    if error:
        log_method(message, extra=context, exc_info=True)
    else:
        log_method(message, extra=context)
