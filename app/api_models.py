"""
API request and response models for the Persian Transcription API.

This module defines Pydantic models for API request validation and
response serialization, ensuring consistent data structures across
all endpoints.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict


class BatchTranscribeResponse(BaseModel):
    """
    Response model for batch transcription job creation.
    
    Returned when a client uploads an audio file for batch processing.
    
    Attributes:
        job_id: Unique identifier for tracking the transcription job
        status: Current job status (typically "pending" for new jobs)
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "pending"
            }
        }
    )
    
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Current job status")


class BatchStatusResponse(BaseModel):
    """
    Response model for batch transcription job status query.
    
    Returned when a client checks the status of a batch transcription job.
    
    Attributes:
        job_id: Unique identifier of the job
        status: Current job status (pending, processing, completed, failed)
        transcription: The transcribed Persian text (only present when completed)
        error: Error message (only present when failed)
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "completed",
                "transcription": "سلام دنیا",
                "error": None
            }
        }
    )
    
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Current job status")
    transcription: Optional[str] = Field(None, description="Transcribed text (when completed)")
    error: Optional[str] = Field(None, description="Error message (when failed)")


class HealthResponse(BaseModel):
    """
    Response model for health check endpoint.
    
    Attributes:
        status: Overall service health status
        model_loaded: Whether the Whisper model is loaded and ready
        model_size: Size of the loaded model (e.g., "small", "medium", "large")
    """
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra={
            "example": {
                "status": "healthy",
                "model_loaded": True,
                "model_size": "medium"
            }
        }
    )
    
    status: str = Field(..., description="Service health status")
    model_loaded: bool = Field(..., description="Whether the model is loaded")
    model_size: str = Field(..., description="Loaded model size")


class ErrorResponse(BaseModel):
    """
    Standard error response model.
    
    All API errors return this consistent structure.
    
    Attributes:
        error: Error details object containing code, message, and optional details
    """
    
    class ErrorDetail(BaseModel):
        """Error detail structure."""
        code: str = Field(..., description="Error code")
        message: str = Field(..., description="Human-readable error message")
        details: Optional[str] = Field(None, description="Additional error context")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": {
                    "code": "UNSUPPORTED_FORMAT",
                    "message": "Audio format not supported. Supported formats: WAV, MP3, OGG, M4A",
                    "details": None
                }
            }
        }
    )
    
    error: ErrorDetail = Field(..., description="Error information")


class StreamTranscriptionMessage(BaseModel):
    """
    WebSocket message model for streaming transcription.
    
    Attributes:
        type: Message type (partial, final, or error)
        text: Transcribed text content
        timestamp: Optional timestamp for the message
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "partial",
                "text": "سلام",
                "timestamp": 1234567890.123
            }
        }
    )
    
    type: Literal["partial", "final", "error"] = Field(..., description="Message type")
    text: str = Field(..., description="Transcription text")
    timestamp: Optional[float] = Field(None, description="Message timestamp")
