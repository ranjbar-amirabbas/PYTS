"""
Job management system for batch transcription processing.

This module provides the JobManager class which handles job lifecycle management,
including creation, status tracking, retrieval, and cleanup of completed jobs.
"""

from datetime import datetime, timedelta
from threading import Lock
from typing import Dict, Optional

from app.models import Job, JobStatus
from app.logging_config import get_logger, log_with_context


class JobManager:
    """
    Manages the lifecycle of batch transcription jobs.
    
    This class provides thread-safe operations for creating, updating, retrieving,
    and cleaning up transcription jobs. Jobs are stored in memory with a dictionary
    keyed by job_id.
    
    Attributes:
        _jobs: Dictionary mapping job_id to Job instances
        _lock: Thread lock for ensuring thread-safe operations
    """
    
    def __init__(self):
        """Initialize the JobManager with an empty job store."""
        self._jobs: Dict[str, Job] = {}
        self._lock = Lock()
        self.logger = get_logger(__name__)
    
    def create_job(self, audio_file_path: str) -> str:
        """
        Create a new transcription job.
        
        Creates a new Job instance with a unique ID and stores it in the job registry.
        The job is initialized with PENDING status.
        
        Args:
            audio_file_path: Path to the audio file to be transcribed
        
        Returns:
            The unique job_id for the newly created job
        
        Example:
            >>> manager = JobManager()
            >>> job_id = manager.create_job("/tmp/audio.wav")
            >>> print(job_id)
            '550e8400-e29b-41d4-a716-446655440000'
        """
        job = Job(audio_file_path=audio_file_path)
        
        with self._lock:
            self._jobs[job.job_id] = job
        
        log_with_context(
            self.logger,
            "info",
            "Job created",
            job_id=job.job_id,
            file_path=audio_file_path
        )
        
        return job.job_id
    
    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        transcription: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        """
        Update the status and results of an existing job.
        
        Updates the job's status and optionally sets the transcription result
        or error message. If the status is COMPLETED or FAILED, the completed_at
        timestamp is automatically set.
        
        Args:
            job_id: The unique identifier of the job to update
            status: The new status to set
            transcription: The transcription result (for COMPLETED status)
            error_message: The error description (for FAILED status)
        
        Raises:
            KeyError: If the job_id does not exist
        
        Example:
            >>> manager.update_job_status(
            ...     job_id="550e8400-e29b-41d4-a716-446655440000",
            ...     status=JobStatus.PROCESSING
            ... )
            >>> manager.update_job_status(
            ...     job_id="550e8400-e29b-41d4-a716-446655440000",
            ...     status=JobStatus.COMPLETED,
            ...     transcription="سلام دنیا"
            ... )
        """
        with self._lock:
            if job_id not in self._jobs:
                log_with_context(
                    self.logger,
                    "error",
                    "Job not found for status update",
                    job_id=job_id
                )
                raise KeyError(f"Job with id {job_id} not found")
            
            job = self._jobs[job_id]
            old_status = job.status
            job.status = status
            
            if transcription is not None:
                job.transcription = transcription
            
            if error_message is not None:
                job.error_message = error_message
            
            # Set completion timestamp for terminal states
            if status in (JobStatus.COMPLETED, JobStatus.FAILED):
                job.completed_at = datetime.utcnow()
            
            # Log status change
            log_context = {
                "job_id": job_id,
                "old_status": old_status.value,
                "new_status": status.value
            }
            
            if error_message:
                log_context["error_message"] = error_message
            
            if transcription:
                log_context["transcription_length"] = len(transcription)
            
            log_with_context(
                self.logger,
                "info",
                "Job status updated",
                **log_context
            )
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Retrieve a job by its unique identifier.
        
        Args:
            job_id: The unique identifier of the job to retrieve
        
        Returns:
            The Job instance if found, None otherwise
        
        Example:
            >>> job = manager.get_job("550e8400-e29b-41d4-a716-446655440000")
            >>> if job:
            ...     print(f"Status: {job.status.value}")
            Status: completed
        """
        with self._lock:
            return self._jobs.get(job_id)
    
    def cleanup_old_jobs(self, max_age_hours: int = 24) -> int:
        """
        Remove completed or failed jobs older than the specified age.
        
        This method helps manage memory by removing old jobs that are no longer
        needed. Only jobs in COMPLETED or FAILED status are eligible for cleanup.
        Jobs in PENDING or PROCESSING status are never removed.
        
        Args:
            max_age_hours: Maximum age in hours for completed jobs (default: 24)
        
        Returns:
            The number of jobs that were removed
        
        Example:
            >>> # Remove jobs completed more than 24 hours ago
            >>> removed_count = manager.cleanup_old_jobs(max_age_hours=24)
            >>> print(f"Removed {removed_count} old jobs")
            Removed 5 old jobs
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        removed_count = 0
        
        with self._lock:
            # Find jobs to remove
            jobs_to_remove = []
            for job_id, job in self._jobs.items():
                # Only cleanup terminal states (COMPLETED or FAILED)
                if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                    # Check if job is old enough
                    if job.completed_at and job.completed_at < cutoff_time:
                        jobs_to_remove.append(job_id)
            
            # Remove the identified jobs
            for job_id in jobs_to_remove:
                del self._jobs[job_id]
                removed_count += 1
        
        if removed_count > 0:
            log_with_context(
                self.logger,
                "info",
                "Cleaned up old jobs",
                removed_count=removed_count,
                max_age_hours=max_age_hours
            )
        
        return removed_count
    
    def get_all_jobs(self) -> Dict[str, Job]:
        """
        Get a copy of all jobs in the system.
        
        This method is primarily useful for testing and debugging.
        
        Returns:
            A dictionary mapping job_id to Job instances
        """
        with self._lock:
            return self._jobs.copy()
    
    def clear_all_jobs(self) -> None:
        """
        Remove all jobs from the system.
        
        This method is primarily useful for testing and cleanup.
        Use with caution in production environments.
        """
        with self._lock:
            self._jobs.clear()
