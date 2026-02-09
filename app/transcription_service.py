"""
Transcription service orchestration for the Persian Transcription API.

This module provides the TranscriptionService class which orchestrates the
complete transcription workflow, integrating audio processing, model inference,
and job management.
"""

from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor
from queue import Queue, Full
import threading

from app.audio_processor import AudioProcessor, UnsupportedFormatError, AudioConversionError
from app.whisper_engine import WhisperEngine, ModelNotReadyError
from app.job_manager import JobManager
from app.models import JobStatus, Job
from app.logging_config import get_logger, log_with_context
from app.config import settings


class TranscriptionService:
    """
    Orchestrates the transcription workflow for batch and streaming processing.
    
    This service integrates the AudioProcessor, WhisperEngine, and JobManager
    to provide a complete transcription solution. It handles:
    - Batch transcription workflow (upload → process → store result)
    - Error handling with descriptive messages
    - Job state tracking
    - Resource cleanup
    - Concurrent request processing with worker pool
    - Request queuing when at capacity
    
    Attributes:
        audio_processor: AudioProcessor instance for format validation and conversion
        whisper_engine: WhisperEngine instance for speech-to-text transcription
        job_manager: JobManager instance for job lifecycle management
        executor: ThreadPoolExecutor for async batch processing
        max_workers: Maximum number of concurrent transcription workers
        max_queue_size: Maximum number of jobs that can be queued
        active_jobs: Number of currently processing jobs
        queued_jobs: Number of jobs waiting in queue
    """
    
    def __init__(
        self,
        audio_processor: Optional[AudioProcessor] = None,
        whisper_engine: Optional[WhisperEngine] = None,
        job_manager: Optional[JobManager] = None,
        max_workers: int = 4,
        max_queue_size: int = 100
    ):
        """
        Initialize the TranscriptionService.
        
        Args:
            audio_processor: AudioProcessor instance (creates new if None)
            whisper_engine: WhisperEngine instance (creates new if None)
            job_manager: JobManager instance (creates new if None)
            max_workers: Maximum number of concurrent transcription workers
            max_queue_size: Maximum number of jobs that can be queued (default: 100)
        """
        self.audio_processor = audio_processor or AudioProcessor()
        self.whisper_engine = whisper_engine or WhisperEngine(model_size=settings.whisper_model_size.value)
        self.job_manager = job_manager or JobManager()
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.logger = get_logger(__name__)
        
        # Track temporary files for cleanup
        self._temp_files: list[Path] = []
        
        # Concurrency control
        self._active_jobs = 0
        self._queued_jobs = 0
        self._concurrency_lock = threading.Lock()
        
        # Job queue for managing capacity
        self._job_queue: Queue = Queue(maxsize=max_queue_size)
    
    def initialize(self) -> None:
        """
        Initialize the transcription service.
        
        This method loads the Whisper model and prepares the service
        for transcription requests.
        
        Raises:
            RuntimeError: If model initialization fails
        """
        self.logger.info("Initializing TranscriptionService")
        
        try:
            # Load the Whisper model
            if not self.whisper_engine.is_ready():
                self.whisper_engine.load_model()
            
            self.logger.info("TranscriptionService initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize TranscriptionService: {str(e)}")
            raise RuntimeError(f"Failed to initialize TranscriptionService: {str(e)}") from e
    
    def is_ready(self) -> bool:
        """
        Check if the service is ready to process transcription requests.
        
        Returns:
            True if the service is ready, False otherwise
        """
        return self.whisper_engine.is_ready()
    
    def is_at_capacity(self) -> bool:
        """
        Check if the service is at capacity and cannot accept more jobs.
        
        Returns:
            True if at capacity (queue is full), False otherwise
        """
        with self._concurrency_lock:
            return self._job_queue.full()
    
    def get_capacity_info(self) -> dict:
        """
        Get information about current capacity and load.
        
        Returns:
            Dictionary with capacity information:
            - active_jobs: Number of currently processing jobs
            - queued_jobs: Number of jobs waiting in queue
            - max_workers: Maximum concurrent workers
            - max_queue_size: Maximum queue size
            - available_capacity: Number of additional jobs that can be queued
        """
        with self._concurrency_lock:
            return {
                "active_jobs": self._active_jobs,
                "queued_jobs": self._queued_jobs,
                "max_workers": self.max_workers,
                "max_queue_size": self.max_queue_size,
                "available_capacity": self.max_queue_size - self._queued_jobs
            }
    
    def transcribe_batch(self, audio_file_path: str) -> str:
        """
        Start a batch transcription job.
        
        This method creates a new job, validates the audio file, and submits
        it for asynchronous processing. The job ID is returned immediately,
        and the client can poll for results using get_batch_status().
        
        If the service is at capacity (queue is full), a RuntimeError is raised
        indicating the server is overloaded.
        
        Workflow:
        1. Check if service is at capacity
        2. Create a new job with PENDING status
        3. Validate audio format
        4. Add job to queue
        5. Submit job for background processing
        6. Return job ID to client
        
        Args:
            audio_file_path: Path to the audio file to transcribe
        
        Returns:
            The unique job_id for tracking the transcription
        
        Raises:
            FileNotFoundError: If the audio file doesn't exist
            UnsupportedFormatError: If the audio format is not supported
            RuntimeError: If the service is not ready or at capacity
        
        Example:
            >>> service = TranscriptionService()
            >>> service.initialize()
            >>> job_id = service.transcribe_batch("/tmp/audio.wav")
            >>> print(job_id)
            '550e8400-e29b-41d4-a716-446655440000'
        """
        if not self.is_ready():
            raise RuntimeError(
                "Transcription service is not ready. Model may still be loading."
            )
        
        # Check if at capacity
        if self.is_at_capacity():
            capacity_info = self.get_capacity_info()
            raise RuntimeError(
                f"Server is at capacity. Active jobs: {capacity_info['active_jobs']}, "
                f"Queued jobs: {capacity_info['queued_jobs']}. Please retry later."
            )
        
        # Validate the audio file exists
        audio_path = Path(audio_file_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")
        
        # Validate the audio format
        try:
            self.audio_processor.validate_format(audio_file_path)
        except UnsupportedFormatError as e:
            self.logger.error(f"Unsupported audio format: {audio_file_path}")
            raise UnsupportedFormatError(
                f"Audio format not supported. Supported formats: WAV, MP3, OGG, M4A"
            ) from e
        
        # Create a new job
        job_id = self.job_manager.create_job(audio_file_path)
        
        self.logger.info(f"Created batch transcription job: {job_id}")
        
        # Add to queue and submit for background processing
        try:
            with self._concurrency_lock:
                self._job_queue.put_nowait(job_id)
                self._queued_jobs += 1
            
            # Submit the job for background processing
            self.executor.submit(self._process_batch_job_with_queue, job_id)
            
        except Full:
            # Queue is full - this shouldn't happen due to earlier check, but handle it
            self.job_manager.update_job_status(
                job_id,
                JobStatus.FAILED,
                error_message="Server is at capacity. Please retry later."
            )
            raise RuntimeError("Server is at capacity. Please retry later.")
        
        return job_id
    
    def _process_batch_job_with_queue(self, job_id: str) -> None:
        """
        Process a batch transcription job with queue management (internal method).
        
        This method wraps the actual job processing with queue management logic:
        1. Remove job from queue
        2. Increment active job counter
        3. Process the job
        4. Decrement active job counter
        
        Args:
            job_id: The unique identifier of the job to process
        """
        try:
            # Remove from queue and mark as active
            with self._concurrency_lock:
                try:
                    self._job_queue.get_nowait()
                    self._queued_jobs -= 1
                    self._active_jobs += 1
                except Exception as e:
                    self.logger.error(f"Error managing queue for job {job_id}: {e}")
            
            # Process the actual job
            self._process_batch_job(job_id)
            
        finally:
            # Decrement active job counter
            with self._concurrency_lock:
                self._active_jobs -= 1
            
            self.logger.debug(
                f"Job {job_id} completed. Active: {self._active_jobs}, "
                f"Queued: {self._queued_jobs}"
            )
    
    def _process_batch_job(self, job_id: str) -> None:
        """
        Process a batch transcription job (internal method).
        
        This method runs in a background thread and performs the complete
        transcription workflow:
        1. Update job status to PROCESSING
        2. Convert audio to Whisper format
        3. Transcribe the audio
        4. Update job with result or error
        5. Clean up temporary files
        
        Args:
            job_id: The unique identifier of the job to process
        """
        converted_audio_path: Optional[Path] = None
        
        try:
            # Get the job
            job = self.job_manager.get_job(job_id)
            if not job:
                log_with_context(
                    self.logger,
                    "error",
                    "Job not found",
                    job_id=job_id
                )
                return
            
            # Update status to PROCESSING
            self.job_manager.update_job_status(job_id, JobStatus.PROCESSING)
            log_with_context(
                self.logger,
                "info",
                "Processing job",
                job_id=job_id,
                file_path=job.audio_file_path
            )
            
            # Convert audio to Whisper format
            try:
                converted_audio_path = self.audio_processor.convert_to_whisper_format(
                    job.audio_file_path
                )
                log_with_context(
                    self.logger,
                    "info",
                    "Audio converted",
                    job_id=job_id,
                    converted_path=str(converted_audio_path)
                )
            except AudioConversionError as e:
                error_msg = f"Failed to convert audio file: {str(e)}"
                log_with_context(
                    self.logger,
                    "error",
                    "Job failed - audio conversion error",
                    job_id=job_id,
                    file_path=job.audio_file_path,
                    error=e
                )
                self.job_manager.update_job_status(
                    job_id,
                    JobStatus.FAILED,
                    error_message=error_msg
                )
                return
            
            # Transcribe the audio
            try:
                transcription = self.whisper_engine.transcribe(str(converted_audio_path))
                log_with_context(
                    self.logger,
                    "info",
                    "Job transcription completed",
                    job_id=job_id,
                    transcription_length=len(transcription)
                )
                
                # Update job with result
                self.job_manager.update_job_status(
                    job_id,
                    JobStatus.COMPLETED,
                    transcription=transcription
                )
                
            except ModelNotReadyError as e:
                error_msg = "Transcription model is not ready"
                log_with_context(
                    self.logger,
                    "error",
                    "Job failed - model not ready",
                    job_id=job_id,
                    error=e
                )
                self.job_manager.update_job_status(
                    job_id,
                    JobStatus.FAILED,
                    error_message=error_msg
                )
            except Exception as e:
                error_msg = f"Transcription failed: {str(e)}"
                log_with_context(
                    self.logger,
                    "error",
                    "Job failed - transcription error",
                    job_id=job_id,
                    error=e
                )
                self.job_manager.update_job_status(
                    job_id,
                    JobStatus.FAILED,
                    error_message=error_msg
                )
        
        except Exception as e:
            # Catch-all for unexpected errors
            error_msg = f"Unexpected error during job processing: {str(e)}"
            log_with_context(
                self.logger,
                "error",
                "Job failed - unexpected error",
                job_id=job_id,
                error=e
            )
            try:
                self.job_manager.update_job_status(
                    job_id,
                    JobStatus.FAILED,
                    error_message=error_msg
                )
            except Exception:
                # If we can't even update the job status, log it
                log_with_context(
                    self.logger,
                    "error",
                    "Failed to update job status",
                    job_id=job_id
                )
        
        finally:
            # Clean up temporary converted audio file
            if converted_audio_path and converted_audio_path.exists():
                try:
                    converted_audio_path.unlink()
                    self.logger.debug(f"Cleaned up temporary file: {converted_audio_path}")
                except Exception as e:
                    log_with_context(
                        self.logger,
                        "warning",
                        "Failed to clean up temporary file",
                        file_path=str(converted_audio_path),
                        error=e
                    )
    
    def get_batch_status(self, job_id: str) -> Optional[Job]:
        """
        Get the status and results of a batch transcription job.
        
        Args:
            job_id: The unique identifier of the job
        
        Returns:
            Job instance if found, None otherwise
        
        Example:
            >>> job = service.get_batch_status("550e8400-e29b-41d4-a716-446655440000")
            >>> if job:
            ...     print(f"Status: {job.status.value}")
            ...     if job.status == JobStatus.COMPLETED:
            ...         print(f"Transcription: {job.transcription}")
            Status: completed
            Transcription: سلام دنیا
        """
        return self.job_manager.get_job(job_id)
    
    def cleanup_old_jobs(self, max_age_hours: int = 24) -> int:
        """
        Clean up old completed or failed jobs.
        
        This method delegates to the JobManager to remove old jobs
        and free up memory.
        
        Args:
            max_age_hours: Maximum age in hours for completed jobs
        
        Returns:
            Number of jobs removed
        """
        removed_count = self.job_manager.cleanup_old_jobs(max_age_hours)
        self.logger.info(f"Cleaned up {removed_count} old jobs")
        return removed_count
    
    def shutdown(self) -> None:
        """
        Shutdown the transcription service.
        
        This method stops accepting new jobs and waits for pending
        jobs to complete before shutting down the executor.
        """
        self.logger.info("Shutting down TranscriptionService")
        
        # Shutdown the executor (wait for pending jobs)
        self.executor.shutdown(wait=True)
        
        # Unload the model to free memory
        self.whisper_engine.unload_model()
        
        self.logger.info("TranscriptionService shutdown complete")
    async def transcribe_stream_chunk(
        self,
        audio_chunk: bytes,
        session_id: Optional[str] = None,
        min_chunk_size: int = 100 * 1024
    ) -> Optional[str]:
        """
        Process an audio chunk for streaming transcription.

        This method handles incremental audio processing for real-time
        transcription. Audio chunks are buffered until they reach a
        minimum size, then transcribed and returned as partial results.

        The method uses the WhisperEngine's streaming capabilities to:
        1. Buffer incoming audio chunks
        2. Transcribe when buffer reaches threshold
        3. Return partial transcription results

        Args:
            audio_chunk: Raw audio data bytes (should be in Whisper-compatible format)
            session_id: Optional session identifier for tracking (currently unused)
            min_chunk_size: Minimum buffer size before transcription (default: 100 KB)

        Returns:
            Partial transcription text if buffer threshold is reached, None otherwise

        Raises:
            RuntimeError: If the service is not ready
            ValueError: If buffer size exceeds maximum limit

        Example:
            >>> service = TranscriptionService()
            >>> service.initialize()
            >>> # Send first chunk
            >>> result1 = await service.transcribe_stream_chunk(audio_chunk_1)
            >>> # result1 might be None if chunk is too small
            >>> # Send second chunk
            >>> result2 = await service.transcribe_stream_chunk(audio_chunk_2)
            >>> # result2 contains partial transcription if buffer threshold reached
            >>> print(result2)
            'سلام'
        """
        if not self.is_ready():
            raise RuntimeError(
                "Transcription service is not ready. Model may still be loading."
            )

        try:
            # Process the chunk using WhisperEngine's streaming method
            result = self.whisper_engine.transcribe_stream(
                audio_chunk=audio_chunk,
                min_chunk_size=min_chunk_size,
                return_partial=True
            )

            if result:
                log_with_context(
                    self.logger,
                    "info",
                    "Streaming transcription partial result",
                    result_length=len(result),
                    session_id=session_id
                )

            return result

        except ValueError as e:
            # Buffer size exceeded
            log_with_context(
                self.logger,
                "error",
                "Streaming buffer error",
                session_id=session_id,
                error=e
            )
            raise
        except Exception as e:
            # Other errors
            error_msg = f"Streaming transcription failed: {str(e)}"
            log_with_context(
                self.logger,
                "error",
                "Streaming transcription failed",
                session_id=session_id,
                error=e
            )
            raise RuntimeError(error_msg) from e

    async def finalize_stream(self, session_id: Optional[str] = None) -> str:
        """
        Finalize a streaming transcription session.

        This method should be called when a WebSocket connection is closed
        to ensure all buffered audio is transcribed. It processes any
        remaining audio data in the buffer and returns the final transcription.

        Args:
            session_id: Optional session identifier for tracking (currently unused)

        Returns:
            Final transcription text from remaining buffer, or empty string if buffer is empty

        Raises:
            RuntimeError: If the service is not ready or finalization fails

        Example:
            >>> # After streaming multiple chunks
            >>> final_text = await service.finalize_stream()
            >>> print(final_text)
            'دنیا'  # Remaining buffered content
        """
        if not self.is_ready():
            raise RuntimeError(
                "Transcription service is not ready. Model may still be loading."
            )

        try:
            self.logger.info("Finalizing streaming transcription session")

            # Finalize the stream using WhisperEngine
            result = self.whisper_engine.finalize_stream()

            if result:
                log_with_context(
                    self.logger,
                    "info",
                    "Streaming transcription finalized",
                    result_length=len(result),
                    session_id=session_id
                )
            else:
                self.logger.info("Streaming transcription finalized with no remaining content")

            return result

        except Exception as e:
            error_msg = f"Stream finalization failed: {str(e)}"
            log_with_context(
                self.logger,
                "error",
                "Stream finalization failed",
                session_id=session_id,
                error=e
            )
            raise RuntimeError(error_msg) from e

    def clear_stream_buffer(self) -> None:
        """
        Clear the streaming buffer.

        This method can be called to reset the streaming state, for example
        when starting a new streaming session or recovering from an error.

        Example:
            >>> service.clear_stream_buffer()
        """
        self.whisper_engine.clear_buffer()
        self.logger.debug("Streaming buffer cleared")

    def get_stream_buffer_size(self) -> int:
        """
        Get the current size of the streaming buffer.

        This can be useful for monitoring buffer usage and debugging.

        Returns:
            Size of buffered audio data in bytes

        Example:
            >>> size = service.get_stream_buffer_size()
            >>> print(f"Buffer size: {size} bytes")
            Buffer size: 51200 bytes
        """
        return self.whisper_engine.get_buffer_size()

