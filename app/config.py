"""
Configuration management for the Persian Transcription API.

This module provides configuration settings for the transcription service,
including worker pool size, queue limits, and other operational parameters.

Uses Pydantic Settings for robust environment variable management with
validation and type safety.
"""

from enum import Enum
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class WhisperModelSize(str, Enum):
    """Supported Whisper model sizes."""
    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class LogLevel(str, Enum):
    """Supported logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    """
    Configuration settings for the transcription service.
    
    All settings can be overridden using environment variables.
    Pydantic Settings provides automatic validation and type conversion.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    # Whisper model configuration
    whisper_model_size: WhisperModelSize = Field(
        default=WhisperModelSize.MEDIUM,
        description="Whisper model size (affects accuracy and performance)",
        alias="WHISPER_MODEL_SIZE"
    )
    
    # Concurrency configuration
    max_concurrent_workers: int = Field(
        default=4,
        ge=1,
        le=32,
        description="Maximum number of concurrent transcription workers",
        alias="MAX_CONCURRENT_WORKERS"
    )
    
    max_queue_size: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum number of jobs that can be queued",
        alias="MAX_QUEUE_SIZE"
    )
    
    # File upload limits
    max_file_size_mb: int = Field(
        default=500,
        ge=1,
        le=5000,
        description="Maximum audio file size in megabytes",
        alias="MAX_FILE_SIZE_MB"
    )
    
    # API configuration
    api_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Port to expose the API",
        alias="API_PORT"
    )
    
    api_host: str = Field(
        default="0.0.0.0",
        description="API host address",
        alias="API_HOST"
    )
    
    # Logging configuration
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Logging level",
        alias="LOG_LEVEL"
    )
    
    # Job cleanup configuration
    job_cleanup_max_age_hours: int = Field(
        default=24,
        ge=1,
        le=720,  # 30 days max
        description="Maximum age of completed jobs before cleanup (in hours)",
        alias="JOB_CLEANUP_MAX_AGE_HOURS"
    )
    
    # Streaming configuration
    stream_min_chunk_size: int = Field(
        default=100 * 1024,  # 100 KB
        ge=1024,  # At least 1 KB
        le=10 * 1024 * 1024,  # At most 10 MB
        description="Minimum chunk size for streaming audio (in bytes)",
        alias="STREAM_MIN_CHUNK_SIZE"
    )
    
    stream_max_buffer_size: int = Field(
        default=10 * 1024 * 1024,  # 10 MB
        ge=100 * 1024,  # At least 100 KB
        le=100 * 1024 * 1024,  # At most 100 MB
        description="Maximum buffer size for streaming audio (in bytes)",
        alias="STREAM_MAX_BUFFER_SIZE"
    )
    
    @field_validator("stream_max_buffer_size")
    @classmethod
    def validate_buffer_size(cls, v: int, info) -> int:
        """Ensure max buffer size is greater than min chunk size."""
        # Note: info.data contains already-validated fields
        min_chunk = info.data.get("stream_min_chunk_size", 100 * 1024)
        if v < min_chunk:
            raise ValueError(
                f"stream_max_buffer_size ({v}) must be >= stream_min_chunk_size ({min_chunk})"
            )
        return v
    
    def get_max_file_size_bytes(self) -> int:
        """Get maximum file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024
    
    def display(self) -> str:
        """
        Get a formatted string of all configuration settings.
        
        Returns:
            Formatted configuration string
        """
        return f"""
Persian Transcription API Configuration:
========================================
Whisper Model Size: {self.whisper_model_size.value}
Max Concurrent Workers: {self.max_concurrent_workers}
Max Queue Size: {self.max_queue_size}
Max File Size: {self.max_file_size_mb} MB
API Host: {self.api_host}
API Port: {self.api_port}
Log Level: {self.log_level.value}
Job Cleanup Max Age: {self.job_cleanup_max_age_hours} hours
Stream Min Chunk Size: {self.stream_min_chunk_size} bytes
Stream Max Buffer Size: {self.stream_max_buffer_size} bytes
"""


# Create a global settings instance
# This will be imported and used throughout the application
settings = Settings()
