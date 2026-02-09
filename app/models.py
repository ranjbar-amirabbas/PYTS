"""
Data models for the Persian Transcription API.

This module defines the core data structures used throughout the application,
including job tracking and status management for batch transcription processing.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4


class JobStatus(Enum):
    """
    Enumeration of possible job processing states.
    
    Attributes:
        PENDING: Job has been created but processing has not started
        PROCESSING: Job is currently being transcribed
        COMPLETED: Job has finished successfully with a transcription result
        FAILED: Job encountered an error during processing
    """
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Job:
    """
    Represents a batch transcription job.
    
    This class tracks the state and results of an audio transcription job
    throughout its lifecycle, from creation through completion or failure.
    
    Attributes:
        job_id: Unique identifier for the job
        status: Current processing state (JobStatus enum)
        audio_file_path: Path to the uploaded audio file
        transcription: The resulting Persian text transcription (None until completed)
        error_message: Error description if job failed (None if successful)
        created_at: Timestamp when the job was created
        completed_at: Timestamp when the job finished (None if still processing)
    """
    
    def __init__(
        self,
        audio_file_path: str,
        job_id: Optional[str] = None,
        status: JobStatus = JobStatus.PENDING,
        transcription: Optional[str] = None,
        error_message: Optional[str] = None,
        created_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None
    ):
        """
        Initialize a new Job instance.
        
        Args:
            audio_file_path: Path to the audio file to be transcribed
            job_id: Unique identifier (auto-generated if not provided)
            status: Initial job status (defaults to PENDING)
            transcription: Transcription result (None for new jobs)
            error_message: Error description (None for new jobs)
            created_at: Creation timestamp (auto-set to now if not provided)
            completed_at: Completion timestamp (None for new jobs)
        """
        self.job_id = job_id or str(uuid4())
        self.status = status
        self.audio_file_path = audio_file_path
        self.transcription = transcription
        self.error_message = error_message
        self.created_at = created_at or datetime.utcnow()
        self.completed_at = completed_at
    
    def to_dict(self) -> dict:
        """
        Convert the Job instance to a dictionary representation.
        
        Returns:
            Dictionary containing all job attributes with serializable values
        """
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "audio_file_path": self.audio_file_path,
            "transcription": self.transcription,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
    
    def __repr__(self) -> str:
        """String representation of the Job for debugging."""
        return (
            f"Job(job_id={self.job_id!r}, status={self.status.value!r}, "
            f"audio_file_path={self.audio_file_path!r})"
        )
