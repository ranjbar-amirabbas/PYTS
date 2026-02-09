"""
Unit tests for the JobManager class.

Tests cover job creation, status updates, retrieval, and cleanup functionality.
"""

import time
from datetime import datetime, timedelta
from threading import Thread

import pytest

from app.job_manager import JobManager
from app.models import Job, JobStatus


class TestJobManager:
    """Test suite for JobManager functionality."""
    
    def test_create_job_returns_unique_id(self):
        """Test that creating a job returns a unique job ID."""
        manager = JobManager()
        job_id = manager.create_job("/tmp/test.wav")
        
        assert job_id is not None
        assert isinstance(job_id, str)
        assert len(job_id) > 0
    
    def test_create_job_generates_different_ids(self):
        """Test that multiple jobs get different unique IDs."""
        manager = JobManager()
        job_id1 = manager.create_job("/tmp/test1.wav")
        job_id2 = manager.create_job("/tmp/test2.wav")
        
        assert job_id1 != job_id2
    
    def test_create_job_initializes_with_pending_status(self):
        """Test that newly created jobs have PENDING status."""
        manager = JobManager()
        job_id = manager.create_job("/tmp/test.wav")
        
        job = manager.get_job(job_id)
        assert job is not None
        assert job.status == JobStatus.PENDING
        assert job.audio_file_path == "/tmp/test.wav"
        assert job.transcription is None
        assert job.error_message is None
        assert job.completed_at is None
    
    def test_get_job_returns_none_for_nonexistent_id(self):
        """Test that getting a non-existent job returns None."""
        manager = JobManager()
        job = manager.get_job("nonexistent-id")
        
        assert job is None
    
    def test_get_job_retrieves_created_job(self):
        """Test that a created job can be retrieved by its ID."""
        manager = JobManager()
        job_id = manager.create_job("/tmp/test.wav")
        
        job = manager.get_job(job_id)
        assert job is not None
        assert job.job_id == job_id
        assert job.audio_file_path == "/tmp/test.wav"
    
    def test_update_job_status_to_processing(self):
        """Test updating a job status to PROCESSING."""
        manager = JobManager()
        job_id = manager.create_job("/tmp/test.wav")
        
        manager.update_job_status(job_id, JobStatus.PROCESSING)
        
        job = manager.get_job(job_id)
        assert job.status == JobStatus.PROCESSING
        assert job.completed_at is None  # Not completed yet
    
    def test_update_job_status_to_completed_with_transcription(self):
        """Test updating a job to COMPLETED with transcription result."""
        manager = JobManager()
        job_id = manager.create_job("/tmp/test.wav")
        
        transcription = "سلام دنیا"
        manager.update_job_status(
            job_id,
            JobStatus.COMPLETED,
            transcription=transcription
        )
        
        job = manager.get_job(job_id)
        assert job.status == JobStatus.COMPLETED
        assert job.transcription == transcription
        assert job.error_message is None
        assert job.completed_at is not None
        assert isinstance(job.completed_at, datetime)
    
    def test_update_job_status_to_failed_with_error(self):
        """Test updating a job to FAILED with error message."""
        manager = JobManager()
        job_id = manager.create_job("/tmp/test.wav")
        
        error_msg = "Audio file is corrupted"
        manager.update_job_status(
            job_id,
            JobStatus.FAILED,
            error_message=error_msg
        )
        
        job = manager.get_job(job_id)
        assert job.status == JobStatus.FAILED
        assert job.error_message == error_msg
        assert job.transcription is None
        assert job.completed_at is not None
    
    def test_update_job_status_raises_error_for_nonexistent_job(self):
        """Test that updating a non-existent job raises KeyError."""
        manager = JobManager()
        
        with pytest.raises(KeyError, match="Job with id nonexistent-id not found"):
            manager.update_job_status("nonexistent-id", JobStatus.PROCESSING)
    
    def test_update_job_status_multiple_times(self):
        """Test that a job can be updated through multiple status transitions."""
        manager = JobManager()
        job_id = manager.create_job("/tmp/test.wav")
        
        # PENDING -> PROCESSING
        manager.update_job_status(job_id, JobStatus.PROCESSING)
        job = manager.get_job(job_id)
        assert job.status == JobStatus.PROCESSING
        
        # PROCESSING -> COMPLETED
        manager.update_job_status(
            job_id,
            JobStatus.COMPLETED,
            transcription="نتیجه"
        )
        job = manager.get_job(job_id)
        assert job.status == JobStatus.COMPLETED
        assert job.transcription == "نتیجه"
    
    def test_cleanup_old_jobs_removes_completed_jobs(self):
        """Test that cleanup removes old completed jobs."""
        manager = JobManager()
        
        # Create a job and mark it as completed
        job_id = manager.create_job("/tmp/test.wav")
        manager.update_job_status(
            job_id,
            JobStatus.COMPLETED,
            transcription="test"
        )
        
        # Manually set the completed_at time to be old
        job = manager.get_job(job_id)
        job.completed_at = datetime.utcnow() - timedelta(hours=25)
        
        # Cleanup jobs older than 24 hours
        removed_count = manager.cleanup_old_jobs(max_age_hours=24)
        
        assert removed_count == 1
        assert manager.get_job(job_id) is None
    
    def test_cleanup_old_jobs_removes_failed_jobs(self):
        """Test that cleanup removes old failed jobs."""
        manager = JobManager()
        
        # Create a job and mark it as failed
        job_id = manager.create_job("/tmp/test.wav")
        manager.update_job_status(
            job_id,
            JobStatus.FAILED,
            error_message="error"
        )
        
        # Manually set the completed_at time to be old
        job = manager.get_job(job_id)
        job.completed_at = datetime.utcnow() - timedelta(hours=25)
        
        # Cleanup jobs older than 24 hours
        removed_count = manager.cleanup_old_jobs(max_age_hours=24)
        
        assert removed_count == 1
        assert manager.get_job(job_id) is None
    
    def test_cleanup_old_jobs_keeps_recent_jobs(self):
        """Test that cleanup does not remove recent completed jobs."""
        manager = JobManager()
        
        # Create a recently completed job
        job_id = manager.create_job("/tmp/test.wav")
        manager.update_job_status(
            job_id,
            JobStatus.COMPLETED,
            transcription="test"
        )
        
        # Cleanup jobs older than 24 hours
        removed_count = manager.cleanup_old_jobs(max_age_hours=24)
        
        assert removed_count == 0
        assert manager.get_job(job_id) is not None
    
    def test_cleanup_old_jobs_keeps_pending_jobs(self):
        """Test that cleanup never removes pending jobs."""
        manager = JobManager()
        
        # Create a pending job
        job_id = manager.create_job("/tmp/test.wav")
        
        # Manually set the created_at time to be old
        job = manager.get_job(job_id)
        job.created_at = datetime.utcnow() - timedelta(hours=25)
        
        # Cleanup should not remove pending jobs
        removed_count = manager.cleanup_old_jobs(max_age_hours=24)
        
        assert removed_count == 0
        assert manager.get_job(job_id) is not None
    
    def test_cleanup_old_jobs_keeps_processing_jobs(self):
        """Test that cleanup never removes processing jobs."""
        manager = JobManager()
        
        # Create a processing job
        job_id = manager.create_job("/tmp/test.wav")
        manager.update_job_status(job_id, JobStatus.PROCESSING)
        
        # Manually set the created_at time to be old
        job = manager.get_job(job_id)
        job.created_at = datetime.utcnow() - timedelta(hours=25)
        
        # Cleanup should not remove processing jobs
        removed_count = manager.cleanup_old_jobs(max_age_hours=24)
        
        assert removed_count == 0
        assert manager.get_job(job_id) is not None
    
    def test_cleanup_old_jobs_with_multiple_jobs(self):
        """Test cleanup with a mix of old and recent jobs."""
        manager = JobManager()
        
        # Create old completed job
        old_job_id = manager.create_job("/tmp/old.wav")
        manager.update_job_status(
            old_job_id,
            JobStatus.COMPLETED,
            transcription="old"
        )
        job = manager.get_job(old_job_id)
        job.completed_at = datetime.utcnow() - timedelta(hours=25)
        
        # Create recent completed job
        recent_job_id = manager.create_job("/tmp/recent.wav")
        manager.update_job_status(
            recent_job_id,
            JobStatus.COMPLETED,
            transcription="recent"
        )
        
        # Create pending job
        pending_job_id = manager.create_job("/tmp/pending.wav")
        
        # Cleanup
        removed_count = manager.cleanup_old_jobs(max_age_hours=24)
        
        assert removed_count == 1
        assert manager.get_job(old_job_id) is None
        assert manager.get_job(recent_job_id) is not None
        assert manager.get_job(pending_job_id) is not None
    
    def test_cleanup_old_jobs_returns_zero_when_no_jobs_to_remove(self):
        """Test that cleanup returns 0 when there are no jobs to remove."""
        manager = JobManager()
        
        removed_count = manager.cleanup_old_jobs(max_age_hours=24)
        assert removed_count == 0
    
    def test_get_all_jobs_returns_all_jobs(self):
        """Test that get_all_jobs returns all jobs in the system."""
        manager = JobManager()
        
        job_id1 = manager.create_job("/tmp/test1.wav")
        job_id2 = manager.create_job("/tmp/test2.wav")
        
        all_jobs = manager.get_all_jobs()
        
        assert len(all_jobs) == 2
        assert job_id1 in all_jobs
        assert job_id2 in all_jobs
    
    def test_clear_all_jobs_removes_all_jobs(self):
        """Test that clear_all_jobs removes all jobs."""
        manager = JobManager()
        
        manager.create_job("/tmp/test1.wav")
        manager.create_job("/tmp/test2.wav")
        
        manager.clear_all_jobs()
        
        all_jobs = manager.get_all_jobs()
        assert len(all_jobs) == 0
    
    def test_thread_safety_concurrent_job_creation(self):
        """Test that concurrent job creation is thread-safe."""
        manager = JobManager()
        job_ids = []
        
        def create_jobs():
            for i in range(10):
                job_id = manager.create_job(f"/tmp/test{i}.wav")
                job_ids.append(job_id)
        
        # Create jobs from multiple threads
        threads = [Thread(target=create_jobs) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        
        # All job IDs should be unique
        assert len(job_ids) == 50
        assert len(set(job_ids)) == 50
    
    def test_thread_safety_concurrent_updates(self):
        """Test that concurrent job updates are thread-safe."""
        manager = JobManager()
        job_id = manager.create_job("/tmp/test.wav")
        
        def update_job():
            for _ in range(10):
                manager.update_job_status(job_id, JobStatus.PROCESSING)
                time.sleep(0.001)
        
        # Update job from multiple threads
        threads = [Thread(target=update_job) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        
        # Job should still be retrievable and in valid state
        job = manager.get_job(job_id)
        assert job is not None
        assert job.status == JobStatus.PROCESSING
