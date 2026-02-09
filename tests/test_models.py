"""
Unit tests for data models.

Tests the Job and JobStatus classes to ensure proper initialization,
state management, and serialization.
"""

import pytest
from datetime import datetime
from app.models import Job, JobStatus


class TestJobStatus:
    """Tests for the JobStatus enum."""
    
    def test_job_status_values(self):
        """Test that JobStatus enum has all required values."""
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.PROCESSING.value == "processing"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"
    
    def test_job_status_enum_members(self):
        """Test that all expected enum members exist."""
        expected_statuses = {"PENDING", "PROCESSING", "COMPLETED", "FAILED"}
        actual_statuses = {status.name for status in JobStatus}
        assert actual_statuses == expected_statuses


class TestJob:
    """Tests for the Job class."""
    
    def test_job_creation_with_defaults(self):
        """Test creating a job with minimal required parameters."""
        audio_path = "/tmp/test_audio.wav"
        job = Job(audio_file_path=audio_path)
        
        assert job.audio_file_path == audio_path
        assert job.status == JobStatus.PENDING
        assert job.transcription is None
        assert job.error_message is None
        assert job.job_id is not None
        assert len(job.job_id) > 0
        assert isinstance(job.created_at, datetime)
        assert job.completed_at is None
    
    def test_job_creation_with_custom_id(self):
        """Test creating a job with a custom job ID."""
        custom_id = "custom-job-123"
        job = Job(audio_file_path="/tmp/test.wav", job_id=custom_id)
        
        assert job.job_id == custom_id
    
    def test_job_creation_with_all_parameters(self):
        """Test creating a job with all parameters specified."""
        job_id = "test-job-456"
        audio_path = "/tmp/audio.mp3"
        status = JobStatus.COMPLETED
        transcription = "این یک متن فارسی است"
        error_msg = None
        created = datetime(2024, 1, 1, 12, 0, 0)
        completed = datetime(2024, 1, 1, 12, 5, 0)
        
        job = Job(
            audio_file_path=audio_path,
            job_id=job_id,
            status=status,
            transcription=transcription,
            error_message=error_msg,
            created_at=created,
            completed_at=completed
        )
        
        assert job.job_id == job_id
        assert job.audio_file_path == audio_path
        assert job.status == status
        assert job.transcription == transcription
        assert job.error_message == error_msg
        assert job.created_at == created
        assert job.completed_at == completed
    
    def test_job_unique_ids(self):
        """Test that auto-generated job IDs are unique."""
        job1 = Job(audio_file_path="/tmp/test1.wav")
        job2 = Job(audio_file_path="/tmp/test2.wav")
        
        assert job1.job_id != job2.job_id
    
    def test_job_to_dict_pending(self):
        """Test serializing a pending job to dictionary."""
        audio_path = "/tmp/test.wav"
        job = Job(audio_file_path=audio_path)
        
        result = job.to_dict()
        
        assert isinstance(result, dict)
        assert result["job_id"] == job.job_id
        assert result["status"] == "pending"
        assert result["audio_file_path"] == audio_path
        assert result["transcription"] is None
        assert result["error_message"] is None
        assert result["created_at"] is not None
        assert result["completed_at"] is None
    
    def test_job_to_dict_completed(self):
        """Test serializing a completed job to dictionary."""
        transcription_text = "سلام دنیا"
        completed_time = datetime(2024, 1, 1, 12, 10, 0)
        
        job = Job(
            audio_file_path="/tmp/test.wav",
            status=JobStatus.COMPLETED,
            transcription=transcription_text,
            completed_at=completed_time
        )
        
        result = job.to_dict()
        
        assert result["status"] == "completed"
        assert result["transcription"] == transcription_text
        assert result["completed_at"] == completed_time.isoformat()
        assert result["error_message"] is None
    
    def test_job_to_dict_failed(self):
        """Test serializing a failed job to dictionary."""
        error_msg = "Audio file is corrupted"
        completed_time = datetime(2024, 1, 1, 12, 15, 0)
        
        job = Job(
            audio_file_path="/tmp/test.wav",
            status=JobStatus.FAILED,
            error_message=error_msg,
            completed_at=completed_time
        )
        
        result = job.to_dict()
        
        assert result["status"] == "failed"
        assert result["error_message"] == error_msg
        assert result["transcription"] is None
        assert result["completed_at"] == completed_time.isoformat()
    
    def test_job_repr(self):
        """Test string representation of Job."""
        job = Job(audio_file_path="/tmp/test.wav", job_id="test-123")
        repr_str = repr(job)
        
        assert "Job(" in repr_str
        assert "test-123" in repr_str
        assert "pending" in repr_str
        assert "/tmp/test.wav" in repr_str
    
    def test_job_status_transitions(self):
        """Test that job status can be updated through its lifecycle."""
        job = Job(audio_file_path="/tmp/test.wav")
        
        # Initial state
        assert job.status == JobStatus.PENDING
        
        # Start processing
        job.status = JobStatus.PROCESSING
        assert job.status == JobStatus.PROCESSING
        
        # Complete successfully
        job.status = JobStatus.COMPLETED
        job.transcription = "نتیجه نهایی"
        job.completed_at = datetime.utcnow()
        assert job.status == JobStatus.COMPLETED
        assert job.transcription is not None
        assert job.completed_at is not None
    
    def test_job_failure_scenario(self):
        """Test job in failed state with error message."""
        job = Job(audio_file_path="/tmp/corrupted.wav")
        
        job.status = JobStatus.FAILED
        job.error_message = "Unsupported audio format"
        job.completed_at = datetime.utcnow()
        
        assert job.status == JobStatus.FAILED
        assert job.error_message is not None
        assert job.transcription is None
        assert job.completed_at is not None
