"""
Unit tests for the configuration module.

Tests configuration loading, validation, and environment variable handling.
"""

import os
import pytest
from pydantic import ValidationError

from app.config import Settings, WhisperModelSize, LogLevel


class TestSettings:
    """Test suite for Settings configuration class."""
    
    def test_default_values(self):
        """Test that default configuration values are set correctly."""
        # Create settings without loading from .env file
        settings = Settings(_env_file=None)
        
        assert settings.whisper_model_size == WhisperModelSize.MEDIUM
        assert settings.max_concurrent_workers == 4
        assert settings.max_queue_size == 100
        assert settings.max_file_size_mb == 500
        assert settings.api_port == 8000
        assert settings.api_host == "0.0.0.0"
        assert settings.log_level == LogLevel.INFO
        assert settings.job_cleanup_max_age_hours == 24
        assert settings.stream_min_chunk_size == 100 * 1024
        assert settings.stream_max_buffer_size == 10 * 1024 * 1024
    
    def test_environment_variable_override(self, monkeypatch):
        """Test that environment variables override default values."""
        monkeypatch.setenv("WHISPER_MODEL_SIZE", "small")
        monkeypatch.setenv("MAX_CONCURRENT_WORKERS", "8")
        monkeypatch.setenv("API_PORT", "9000")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        
        settings = Settings(_env_file=None)
        
        assert settings.whisper_model_size == WhisperModelSize.SMALL
        assert settings.max_concurrent_workers == 8
        assert settings.api_port == 9000
        assert settings.log_level == LogLevel.DEBUG
    
    def test_get_max_file_size_bytes(self):
        """Test conversion of file size from MB to bytes."""
        settings = Settings(_env_file=None)
        
        # Default is 500 MB
        assert settings.get_max_file_size_bytes() == 500 * 1024 * 1024
    
    def test_display_method(self):
        """Test that display method returns formatted configuration string."""
        settings = Settings(_env_file=None)
        display_str = settings.display()
        
        assert "Persian Transcription API Configuration" in display_str
        assert "Whisper Model Size:" in display_str
        assert "Max Concurrent Workers:" in display_str
        assert "API Port:" in display_str
        assert str(settings.api_port) in display_str
    
    def test_whisper_model_size_enum_values(self):
        """Test that WhisperModelSize enum has all expected values."""
        assert WhisperModelSize.TINY.value == "tiny"
        assert WhisperModelSize.BASE.value == "base"
        assert WhisperModelSize.SMALL.value == "small"
        assert WhisperModelSize.MEDIUM.value == "medium"
        assert WhisperModelSize.LARGE.value == "large"
    
    def test_log_level_enum_values(self):
        """Test that LogLevel enum has all expected values."""
        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.WARNING.value == "WARNING"
        assert LogLevel.ERROR.value == "ERROR"
        assert LogLevel.CRITICAL.value == "CRITICAL"


class TestConfigurationIntegration:
    """Integration tests for configuration usage."""
    
    def test_configuration_for_requirement_6_4(self):
        """
        Test that configuration supports requirement 6.4:
        'THE Docker_Container SHALL expose the REST_API on a configurable port'
        
        Requirements 6.4: THE Docker_Container SHALL expose the REST_API on a configurable port
        """
        # Test default port
        settings = Settings(_env_file=None)
        assert settings.api_port == 8000
        
        # Verify port is configurable and within valid range
        assert 1 <= settings.api_port <= 65535
        assert hasattr(settings, 'api_port')
        assert hasattr(settings, 'api_host')
    
    def test_configuration_for_requirement_10_4(self):
        """
        Test that configuration supports requirement 10.4:
        'THE Transcription_Service SHALL support concurrent request processing
        based on available resources'
        
        Requirements 10.4: THE Transcription_Service SHALL support concurrent request 
        processing based on available resources
        """
        # Test default concurrency settings
        settings = Settings(_env_file=None)
        assert settings.max_concurrent_workers == 4
        assert settings.max_queue_size == 100
        
        # Verify concurrency is configurable and within valid ranges
        assert 1 <= settings.max_concurrent_workers <= 32
        assert 1 <= settings.max_queue_size <= 10000
        
        # Verify the configuration has all necessary fields for concurrency
        assert hasattr(settings, 'max_concurrent_workers')
        assert hasattr(settings, 'max_queue_size')
    
    def test_all_required_configuration_options_present(self):
        """Test that all required configuration options are available."""
        settings = Settings(_env_file=None)
        
        # Model configuration
        assert hasattr(settings, 'whisper_model_size')
        
        # Concurrency configuration (Requirement 10.4)
        assert hasattr(settings, 'max_concurrent_workers')
        assert hasattr(settings, 'max_queue_size')
        
        # File limits
        assert hasattr(settings, 'max_file_size_mb')
        
        # API configuration (Requirement 6.4)
        assert hasattr(settings, 'api_port')
        assert hasattr(settings, 'api_host')
        
        # Logging
        assert hasattr(settings, 'log_level')
        
        # Job management
        assert hasattr(settings, 'job_cleanup_max_age_hours')
        
        # Streaming
        assert hasattr(settings, 'stream_min_chunk_size')
        assert hasattr(settings, 'stream_max_buffer_size')
    
    def test_configuration_can_be_overridden_via_env(self, monkeypatch):
        """Test that all configuration can be overridden via environment variables."""
        # Set environment variables
        monkeypatch.setenv("WHISPER_MODEL_SIZE", "large")
        monkeypatch.setenv("MAX_CONCURRENT_WORKERS", "16")
        monkeypatch.setenv("MAX_QUEUE_SIZE", "500")
        monkeypatch.setenv("MAX_FILE_SIZE_MB", "1000")
        monkeypatch.setenv("API_PORT", "9000")
        monkeypatch.setenv("API_HOST", "127.0.0.1")
        monkeypatch.setenv("LOG_LEVEL", "WARNING")
        monkeypatch.setenv("JOB_CLEANUP_MAX_AGE_HOURS", "48")
        monkeypatch.setenv("STREAM_MIN_CHUNK_SIZE", "200000")
        monkeypatch.setenv("STREAM_MAX_BUFFER_SIZE", "20000000")
        
        settings = Settings(_env_file=None)
        
        # Verify all settings were overridden
        assert settings.whisper_model_size == WhisperModelSize.LARGE
        assert settings.max_concurrent_workers == 16
        assert settings.max_queue_size == 500
        assert settings.max_file_size_mb == 1000
        assert settings.api_port == 9000
        assert settings.api_host == "127.0.0.1"
        assert settings.log_level == LogLevel.WARNING
        assert settings.job_cleanup_max_age_hours == 48
        assert settings.stream_min_chunk_size == 200000
        assert settings.stream_max_buffer_size == 20000000

