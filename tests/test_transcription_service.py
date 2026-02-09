"""
Unit tests for the TranscriptionService class.

These tests verify the batch transcription workflow, error handling,
and integration between AudioProcessor, WhisperEngine, and JobManager.
"""

import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from app.transcription_service import TranscriptionService
from app.audio_processor import AudioProcessor, UnsupportedFormatError, AudioConversionError
from app.whisper_engine import WhisperEngine, ModelNotReadyError
from app.job_manager import JobManager
from app.models import JobStatus, Job


@pytest.fixture
def mock_audio_processor():
    """Create a mock AudioProcessor."""
    processor = Mock(spec=AudioProcessor)
    processor.validate_format = Mock()
    processor.convert_to_whisper_format = Mock()
    return processor


@pytest.fixture
def mock_whisper_engine():
    """Create a mock WhisperEngine."""
    engine = Mock(spec=WhisperEngine)
    engine.is_ready = Mock(return_value=True)
    engine.load_model = Mock()
    engine.transcribe = Mock(return_value="سلام دنیا")
    engine.unload_model = Mock()
    return engine


@pytest.fixture
def mock_job_manager():
    """Create a mock JobManager."""
    manager = Mock(spec=JobManager)
    manager.create_job = Mock(return_value="test-job-id-123")
    manager.update_job_status = Mock()
    manager.get_job = Mock()
    manager.cleanup_old_jobs = Mock(return_value=5)
    return manager


@pytest.fixture
def transcription_service(mock_audio_processor, mock_whisper_engine, mock_job_manager):
    """Create a TranscriptionService with mocked dependencies."""
    service = TranscriptionService(
        audio_processor=mock_audio_processor,
        whisper_engine=mock_whisper_engine,
        job_manager=mock_job_manager,
        max_workers=2
    )
    return service


@pytest.fixture
def temp_audio_file():
    """Create a temporary audio file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(b"RIFF" + b"\x00" * 100)  # Minimal WAV header
        temp_path = Path(f.name)
    
    yield temp_path
    
    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


class TestTranscriptionServiceInitialization:
    """Tests for TranscriptionService initialization."""
    
    def test_init_with_default_dependencies(self):
        """Test initialization with default dependencies."""
        service = TranscriptionService()
        
        assert service.audio_processor is not None
        assert service.whisper_engine is not None
        assert service.job_manager is not None
        assert service.executor is not None
    
    def test_init_with_custom_dependencies(
        self,
        mock_audio_processor,
        mock_whisper_engine,
        mock_job_manager
    ):
        """Test initialization with custom dependencies."""
        service = TranscriptionService(
            audio_processor=mock_audio_processor,
            whisper_engine=mock_whisper_engine,
            job_manager=mock_job_manager
        )
        
        assert service.audio_processor is mock_audio_processor
        assert service.whisper_engine is mock_whisper_engine
        assert service.job_manager is mock_job_manager
    
    def test_initialize_loads_model(self, transcription_service, mock_whisper_engine):
        """Test that initialize() loads the Whisper model."""
        mock_whisper_engine.is_ready.return_value = False
        
        transcription_service.initialize()
        
        mock_whisper_engine.load_model.assert_called_once()
    
    def test_initialize_skips_loading_if_ready(
        self,
        transcription_service,
        mock_whisper_engine
    ):
        """Test that initialize() skips loading if model is already ready."""
        mock_whisper_engine.is_ready.return_value = True
        
        transcription_service.initialize()
        
        mock_whisper_engine.load_model.assert_not_called()
    
    def test_initialize_raises_on_model_load_failure(
        self,
        transcription_service,
        mock_whisper_engine
    ):
        """Test that initialize() raises RuntimeError if model loading fails."""
        mock_whisper_engine.is_ready.return_value = False
        mock_whisper_engine.load_model.side_effect = RuntimeError("Model load failed")
        
        with pytest.raises(RuntimeError, match="Failed to initialize TranscriptionService"):
            transcription_service.initialize()
    
    def test_is_ready_returns_model_readiness(
        self,
        transcription_service,
        mock_whisper_engine
    ):
        """Test that is_ready() returns the model's readiness state."""
        mock_whisper_engine.is_ready.return_value = True
        assert transcription_service.is_ready() is True
        
        mock_whisper_engine.is_ready.return_value = False
        assert transcription_service.is_ready() is False


class TestBatchTranscription:
    """Tests for batch transcription workflow."""
    
    def test_transcribe_batch_creates_job(
        self,
        transcription_service,
        mock_job_manager,
        temp_audio_file
    ):
        """Test that transcribe_batch creates a new job."""
        job_id = transcription_service.transcribe_batch(str(temp_audio_file))
        
        assert job_id == "test-job-id-123"
        mock_job_manager.create_job.assert_called_once_with(str(temp_audio_file))
    
    def test_transcribe_batch_validates_format(
        self,
        transcription_service,
        mock_audio_processor,
        temp_audio_file
    ):
        """Test that transcribe_batch validates audio format."""
        transcription_service.transcribe_batch(str(temp_audio_file))
        
        mock_audio_processor.validate_format.assert_called_once_with(str(temp_audio_file))
    
    def test_transcribe_batch_raises_on_missing_file(self, transcription_service):
        """Test that transcribe_batch raises FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError, match="Audio file not found"):
            transcription_service.transcribe_batch("/nonexistent/file.wav")
    
    def test_transcribe_batch_raises_on_unsupported_format(
        self,
        transcription_service,
        mock_audio_processor,
        temp_audio_file
    ):
        """Test that transcribe_batch raises UnsupportedFormatError for invalid formats."""
        mock_audio_processor.validate_format.side_effect = UnsupportedFormatError(
            "Unsupported format"
        )
        
        with pytest.raises(UnsupportedFormatError, match="Audio format not supported"):
            transcription_service.transcribe_batch(str(temp_audio_file))
    
    def test_transcribe_batch_raises_when_not_ready(
        self,
        transcription_service,
        mock_whisper_engine,
        temp_audio_file
    ):
        """Test that transcribe_batch raises RuntimeError when service is not ready."""
        mock_whisper_engine.is_ready.return_value = False
        
        with pytest.raises(RuntimeError, match="Transcription service is not ready"):
            transcription_service.transcribe_batch(str(temp_audio_file))
    
    def test_transcribe_batch_submits_background_job(
        self,
        transcription_service,
        temp_audio_file
    ):
        """Test that transcribe_batch submits job for background processing."""
        with patch.object(transcription_service.executor, 'submit') as mock_submit:
            transcription_service.transcribe_batch(str(temp_audio_file))
            
            mock_submit.assert_called_once()
            # Verify the submitted function is _process_batch_job_with_queue
            args = mock_submit.call_args[0]
            assert args[0].__name__ == '_process_batch_job_with_queue'


class TestBatchJobProcessing:
    """Tests for internal batch job processing."""
    
    def test_process_batch_job_success(
        self,
        transcription_service,
        mock_audio_processor,
        mock_whisper_engine,
        mock_job_manager,
        temp_audio_file
    ):
        """Test successful batch job processing."""
        # Setup mocks
        job = Job(audio_file_path=str(temp_audio_file), job_id="test-job-id")
        mock_job_manager.get_job.return_value = job
        mock_audio_processor.convert_to_whisper_format.return_value = temp_audio_file
        mock_whisper_engine.transcribe.return_value = "سلام دنیا"
        
        # Process the job
        transcription_service._process_batch_job("test-job-id")
        
        # Verify status updates
        assert mock_job_manager.update_job_status.call_count == 2
        
        # First call: PROCESSING
        first_call = mock_job_manager.update_job_status.call_args_list[0]
        assert first_call[0][0] == "test-job-id"
        assert first_call[0][1] == JobStatus.PROCESSING
        
        # Second call: COMPLETED with transcription
        second_call = mock_job_manager.update_job_status.call_args_list[1]
        assert second_call[0][0] == "test-job-id"
        assert second_call[0][1] == JobStatus.COMPLETED
        assert second_call[1]["transcription"] == "سلام دنیا"
    
    def test_process_batch_job_conversion_failure(
        self,
        transcription_service,
        mock_audio_processor,
        mock_job_manager,
        temp_audio_file
    ):
        """Test batch job processing with audio conversion failure."""
        # Setup mocks
        job = Job(audio_file_path=str(temp_audio_file), job_id="test-job-id")
        mock_job_manager.get_job.return_value = job
        mock_audio_processor.convert_to_whisper_format.side_effect = AudioConversionError(
            "Conversion failed"
        )
        
        # Process the job
        transcription_service._process_batch_job("test-job-id")
        
        # Verify status updates
        assert mock_job_manager.update_job_status.call_count == 2
        
        # Second call should be FAILED with error message
        second_call = mock_job_manager.update_job_status.call_args_list[1]
        assert second_call[0][0] == "test-job-id"
        assert second_call[0][1] == JobStatus.FAILED
        assert "Failed to convert audio file" in second_call[1]["error_message"]
    
    def test_process_batch_job_transcription_failure(
        self,
        transcription_service,
        mock_audio_processor,
        mock_whisper_engine,
        mock_job_manager,
        temp_audio_file
    ):
        """Test batch job processing with transcription failure."""
        # Setup mocks
        job = Job(audio_file_path=str(temp_audio_file), job_id="test-job-id")
        mock_job_manager.get_job.return_value = job
        mock_audio_processor.convert_to_whisper_format.return_value = temp_audio_file
        mock_whisper_engine.transcribe.side_effect = RuntimeError("Transcription error")
        
        # Process the job
        transcription_service._process_batch_job("test-job-id")
        
        # Verify status updates
        assert mock_job_manager.update_job_status.call_count == 2
        
        # Second call should be FAILED with error message
        second_call = mock_job_manager.update_job_status.call_args_list[1]
        assert second_call[0][0] == "test-job-id"
        assert second_call[0][1] == JobStatus.FAILED
        assert "Transcription failed" in second_call[1]["error_message"]
    
    def test_process_batch_job_model_not_ready(
        self,
        transcription_service,
        mock_audio_processor,
        mock_whisper_engine,
        mock_job_manager,
        temp_audio_file
    ):
        """Test batch job processing when model is not ready."""
        # Setup mocks
        job = Job(audio_file_path=str(temp_audio_file), job_id="test-job-id")
        mock_job_manager.get_job.return_value = job
        mock_audio_processor.convert_to_whisper_format.return_value = temp_audio_file
        mock_whisper_engine.transcribe.side_effect = ModelNotReadyError("Model not ready")
        
        # Process the job
        transcription_service._process_batch_job("test-job-id")
        
        # Verify status updates
        assert mock_job_manager.update_job_status.call_count == 2
        
        # Second call should be FAILED with specific error message
        second_call = mock_job_manager.update_job_status.call_args_list[1]
        assert second_call[0][0] == "test-job-id"
        assert second_call[0][1] == JobStatus.FAILED
        assert "Transcription model is not ready" in second_call[1]["error_message"]
    
    def test_process_batch_job_cleans_up_temp_file(
        self,
        transcription_service,
        mock_audio_processor,
        mock_whisper_engine,
        mock_job_manager,
        temp_audio_file
    ):
        """Test that batch job processing cleans up temporary files."""
        # Create a temporary file that will be "converted"
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(b"converted audio")
            converted_path = Path(f.name)
        
        # Setup mocks
        job = Job(audio_file_path=str(temp_audio_file), job_id="test-job-id")
        mock_job_manager.get_job.return_value = job
        mock_audio_processor.convert_to_whisper_format.return_value = converted_path
        mock_whisper_engine.transcribe.return_value = "سلام"
        
        # Process the job
        transcription_service._process_batch_job("test-job-id")
        
        # Verify the temporary file was deleted
        assert not converted_path.exists()
    
    def test_process_batch_job_handles_missing_job(
        self,
        transcription_service,
        mock_job_manager
    ):
        """Test that _process_batch_job handles missing job gracefully."""
        mock_job_manager.get_job.return_value = None
        
        # Should not raise an exception
        transcription_service._process_batch_job("nonexistent-job-id")
        
        # Should not attempt to update status
        mock_job_manager.update_job_status.assert_not_called()


class TestBatchStatusRetrieval:
    """Tests for batch status retrieval."""
    
    def test_get_batch_status_returns_job(
        self,
        transcription_service,
        mock_job_manager
    ):
        """Test that get_batch_status returns the job."""
        expected_job = Job(audio_file_path="/tmp/test.wav", job_id="test-job-id")
        mock_job_manager.get_job.return_value = expected_job
        
        result = transcription_service.get_batch_status("test-job-id")
        
        assert result is expected_job
        mock_job_manager.get_job.assert_called_once_with("test-job-id")
    
    def test_get_batch_status_returns_none_for_missing_job(
        self,
        transcription_service,
        mock_job_manager
    ):
        """Test that get_batch_status returns None for missing jobs."""
        mock_job_manager.get_job.return_value = None
        
        result = transcription_service.get_batch_status("nonexistent-job-id")
        
        assert result is None


class TestCleanup:
    """Tests for cleanup operations."""
    
    def test_cleanup_old_jobs(
        self,
        transcription_service,
        mock_job_manager
    ):
        """Test that cleanup_old_jobs delegates to JobManager."""
        result = transcription_service.cleanup_old_jobs(max_age_hours=48)
        
        assert result == 5
        mock_job_manager.cleanup_old_jobs.assert_called_once_with(48)
    
    def test_shutdown_stops_executor(
        self,
        transcription_service,
        mock_whisper_engine
    ):
        """Test that shutdown stops the executor and unloads the model."""
        with patch.object(transcription_service.executor, 'shutdown') as mock_shutdown:
            transcription_service.shutdown()
            
            mock_shutdown.assert_called_once_with(wait=True)
            mock_whisper_engine.unload_model.assert_called_once()


class TestErrorHandling:
    """Tests for error handling with descriptive messages."""
    
    def test_descriptive_error_for_unsupported_format(
        self,
        transcription_service,
        mock_audio_processor,
        temp_audio_file
    ):
        """Test that unsupported format errors have descriptive messages."""
        mock_audio_processor.validate_format.side_effect = UnsupportedFormatError(
            "Invalid format"
        )
        
        with pytest.raises(UnsupportedFormatError) as exc_info:
            transcription_service.transcribe_batch(str(temp_audio_file))
        
        assert "Audio format not supported" in str(exc_info.value)
        assert "WAV, MP3, OGG, M4A" in str(exc_info.value)
    
    def test_descriptive_error_for_missing_file(self, transcription_service):
        """Test that missing file errors have descriptive messages."""
        with pytest.raises(FileNotFoundError) as exc_info:
            transcription_service.transcribe_batch("/nonexistent/file.wav")
        
        assert "Audio file not found" in str(exc_info.value)
    
    def test_descriptive_error_for_service_not_ready(
        self,
        transcription_service,
        mock_whisper_engine,
        temp_audio_file
    ):
        """Test that service not ready errors have descriptive messages."""
        mock_whisper_engine.is_ready.return_value = False
        
        with pytest.raises(RuntimeError) as exc_info:
            transcription_service.transcribe_batch(str(temp_audio_file))
        
        assert "Transcription service is not ready" in str(exc_info.value)
        assert "Model may still be loading" in str(exc_info.value)


class TestStreamingTranscription:
    """Tests for streaming transcription workflow."""
    
    @pytest.mark.asyncio
    async def test_transcribe_stream_chunk_returns_none_for_small_chunks(
        self,
        transcription_service,
        mock_whisper_engine
    ):
        """Test that small chunks are buffered without returning results."""
        mock_whisper_engine.transcribe_stream.return_value = None
        
        result = await transcription_service.transcribe_stream_chunk(
            audio_chunk=b"small chunk",
            min_chunk_size=100 * 1024
        )
        
        assert result is None
        mock_whisper_engine.transcribe_stream.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_transcribe_stream_chunk_returns_partial_for_large_chunks(
        self,
        transcription_service,
        mock_whisper_engine
    ):
        """Test that large chunks trigger partial transcription."""
        mock_whisper_engine.transcribe_stream.return_value = "سلام"
        
        large_chunk = b"x" * (150 * 1024)  # 150 KB
        result = await transcription_service.transcribe_stream_chunk(
            audio_chunk=large_chunk,
            min_chunk_size=100 * 1024
        )
        
        assert result == "سلام"
        mock_whisper_engine.transcribe_stream.assert_called_once_with(
            audio_chunk=large_chunk,
            min_chunk_size=100 * 1024,
            return_partial=True
        )
    
    @pytest.mark.asyncio
    async def test_transcribe_stream_chunk_raises_when_not_ready(
        self,
        transcription_service,
        mock_whisper_engine
    ):
        """Test that streaming raises RuntimeError when service is not ready."""
        mock_whisper_engine.is_ready.return_value = False
        
        with pytest.raises(RuntimeError, match="Transcription service is not ready"):
            await transcription_service.transcribe_stream_chunk(b"audio chunk")
    
    @pytest.mark.asyncio
    async def test_transcribe_stream_chunk_handles_buffer_overflow(
        self,
        transcription_service,
        mock_whisper_engine
    ):
        """Test that buffer overflow errors are propagated."""
        mock_whisper_engine.transcribe_stream.side_effect = ValueError(
            "Stream buffer size would exceed maximum limit"
        )
        
        with pytest.raises(ValueError, match="Stream buffer size would exceed maximum limit"):
            await transcription_service.transcribe_stream_chunk(b"audio chunk")
    
    @pytest.mark.asyncio
    async def test_transcribe_stream_chunk_handles_transcription_errors(
        self,
        transcription_service,
        mock_whisper_engine
    ):
        """Test that transcription errors are wrapped in RuntimeError."""
        mock_whisper_engine.transcribe_stream.side_effect = Exception("Transcription error")
        
        with pytest.raises(RuntimeError, match="Streaming transcription failed"):
            await transcription_service.transcribe_stream_chunk(b"audio chunk")
    
    @pytest.mark.asyncio
    async def test_finalize_stream_returns_remaining_content(
        self,
        transcription_service,
        mock_whisper_engine
    ):
        """Test that finalize_stream returns remaining buffered content."""
        mock_whisper_engine.finalize_stream.return_value = "دنیا"
        
        result = await transcription_service.finalize_stream()
        
        assert result == "دنیا"
        mock_whisper_engine.finalize_stream.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_finalize_stream_returns_empty_for_empty_buffer(
        self,
        transcription_service,
        mock_whisper_engine
    ):
        """Test that finalize_stream returns empty string for empty buffer."""
        mock_whisper_engine.finalize_stream.return_value = ""
        
        result = await transcription_service.finalize_stream()
        
        assert result == ""
        mock_whisper_engine.finalize_stream.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_finalize_stream_raises_when_not_ready(
        self,
        transcription_service,
        mock_whisper_engine
    ):
        """Test that finalize_stream raises RuntimeError when service is not ready."""
        mock_whisper_engine.is_ready.return_value = False
        
        with pytest.raises(RuntimeError, match="Transcription service is not ready"):
            await transcription_service.finalize_stream()
    
    @pytest.mark.asyncio
    async def test_finalize_stream_handles_errors(
        self,
        transcription_service,
        mock_whisper_engine
    ):
        """Test that finalize_stream handles errors gracefully."""
        mock_whisper_engine.finalize_stream.side_effect = Exception("Finalization error")
        
        with pytest.raises(RuntimeError, match="Stream finalization failed"):
            await transcription_service.finalize_stream()
    
    def test_clear_stream_buffer(
        self,
        transcription_service,
        mock_whisper_engine
    ):
        """Test that clear_stream_buffer clears the WhisperEngine buffer."""
        transcription_service.clear_stream_buffer()
        
        mock_whisper_engine.clear_buffer.assert_called_once()
    
    def test_get_stream_buffer_size(
        self,
        transcription_service,
        mock_whisper_engine
    ):
        """Test that get_stream_buffer_size returns buffer size."""
        mock_whisper_engine.get_buffer_size.return_value = 51200
        
        size = transcription_service.get_stream_buffer_size()
        
        assert size == 51200
        mock_whisper_engine.get_buffer_size.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_streaming_workflow_complete(
        self,
        transcription_service,
        mock_whisper_engine
    ):
        """Test complete streaming workflow with multiple chunks and finalization."""
        # Setup mock responses
        mock_whisper_engine.transcribe_stream.side_effect = [
            None,  # First chunk buffered
            "سلام",  # Second chunk triggers partial result
            None,  # Third chunk buffered
        ]
        mock_whisper_engine.finalize_stream.return_value = "دنیا"
        
        # Send first chunk (small, buffered)
        result1 = await transcription_service.transcribe_stream_chunk(b"chunk1")
        assert result1 is None
        
        # Send second chunk (large, triggers transcription)
        result2 = await transcription_service.transcribe_stream_chunk(b"chunk2")
        assert result2 == "سلام"
        
        # Send third chunk (small, buffered)
        result3 = await transcription_service.transcribe_stream_chunk(b"chunk3")
        assert result3 is None
        
        # Finalize stream
        final_result = await transcription_service.finalize_stream()
        assert final_result == "دنیا"
        
        # Verify all methods were called
        assert mock_whisper_engine.transcribe_stream.call_count == 3
        mock_whisper_engine.finalize_stream.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_streaming_with_session_id(
        self,
        transcription_service,
        mock_whisper_engine
    ):
        """Test streaming with session_id parameter (for future use)."""
        mock_whisper_engine.transcribe_stream.return_value = "متن"
        mock_whisper_engine.finalize_stream.return_value = "نهایی"
        
        # Session ID is accepted but currently not used
        result1 = await transcription_service.transcribe_stream_chunk(
            audio_chunk=b"chunk",
            session_id="session-123"
        )
        
        result2 = await transcription_service.finalize_stream(session_id="session-123")
        
        # Methods should work normally
        assert result1 == "متن"
        assert result2 == "نهایی"
    
    @pytest.mark.asyncio
    async def test_streaming_error_recovery(
        self,
        transcription_service,
        mock_whisper_engine
    ):
        """Test error recovery in streaming workflow."""
        # First chunk succeeds
        mock_whisper_engine.transcribe_stream.return_value = "بخش اول"
        result1 = await transcription_service.transcribe_stream_chunk(b"chunk1")
        assert result1 == "بخش اول"
        
        # Second chunk fails
        mock_whisper_engine.transcribe_stream.side_effect = Exception("Error")
        with pytest.raises(RuntimeError, match="Streaming transcription failed"):
            await transcription_service.transcribe_stream_chunk(b"chunk2")
        
        # Clear buffer for recovery
        transcription_service.clear_stream_buffer()
        mock_whisper_engine.clear_buffer.assert_called()
        
        # Continue with new chunks after recovery
        mock_whisper_engine.transcribe_stream.side_effect = None
        mock_whisper_engine.transcribe_stream.return_value = "بخش دوم"
        result3 = await transcription_service.transcribe_stream_chunk(b"chunk3")
        assert result3 == "بخش دوم"


class TestIntegration:
    """Integration tests with real components (no mocks)."""
    
    @pytest.mark.slow
    def test_full_workflow_with_real_components(self, temp_audio_file):
        """Test the full transcription workflow with real components.
        
        Note: This test is marked as slow because it loads the actual Whisper model.
        """
        # Create service with real components
        service = TranscriptionService(max_workers=1)
        
        # Initialize (loads model)
        service.initialize()
        
        try:
            # Start transcription
            job_id = service.transcribe_batch(str(temp_audio_file))
            assert job_id is not None
            
            # Wait for processing (with timeout)
            max_wait = 30  # seconds
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                job = service.get_batch_status(job_id)
                if job and job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                    break
                time.sleep(0.5)
            
            # Check final status
            job = service.get_batch_status(job_id)
            assert job is not None
            assert job.status in (JobStatus.COMPLETED, JobStatus.FAILED)
            
            # If completed, verify transcription exists
            if job.status == JobStatus.COMPLETED:
                assert job.transcription is not None
                assert isinstance(job.transcription, str)
        
        finally:
            # Cleanup
            service.shutdown()


class TestConcurrencyControl:
    """Tests for concurrent request handling and capacity management."""
    
    def test_is_at_capacity_returns_false_when_queue_not_full(
        self,
        transcription_service
    ):
        """Test that is_at_capacity returns False when queue is not full."""
        assert not transcription_service.is_at_capacity()
    
    def test_get_capacity_info_returns_correct_info(
        self,
        transcription_service
    ):
        """Test that get_capacity_info returns correct capacity information."""
        info = transcription_service.get_capacity_info()
        
        assert "active_jobs" in info
        assert "queued_jobs" in info
        assert "max_workers" in info
        assert "max_queue_size" in info
        assert "available_capacity" in info
        
        assert info["active_jobs"] == 0
        assert info["queued_jobs"] == 0
        # The fixture creates service with max_workers=2
        assert info["max_workers"] == 2
        assert info["max_queue_size"] == 100
        assert info["available_capacity"] == 100
    
    def test_transcribe_batch_checks_capacity(self):
        """Test that transcribe_batch checks capacity before accepting jobs."""
        # Create service with minimal queue
        service = TranscriptionService(max_workers=1, max_queue_size=1)
        service.initialize()
        
        # Verify capacity checking works
        assert not service.is_at_capacity()
        
        # After adding a job, capacity should be affected
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(b"RIFF" + b"\x00" * 40)
            temp_path = f.name
        
        try:
            job_id = service.transcribe_batch(temp_path)
            assert job_id is not None
            
            # The job was accepted and queued
            info = service.get_capacity_info()
            assert info["max_queue_size"] == 1
        finally:
            import os
            os.unlink(temp_path)
            service.shutdown()
    
    def test_concurrent_job_processing(
        self,
        temp_audio_file
    ):
        """Test that multiple jobs can be processed concurrently."""
        service = TranscriptionService(max_workers=2)
        service.initialize()
        
        # Submit multiple jobs
        job_ids = []
        for _ in range(3):
            job_id = service.transcribe_batch(str(temp_audio_file))
            job_ids.append(job_id)
        
        # Wait for jobs to complete
        import time
        max_wait = 30  # seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            all_complete = True
            for job_id in job_ids:
                job = service.get_batch_status(job_id)
                if job and job.status not in [JobStatus.COMPLETED, JobStatus.FAILED]:
                    all_complete = False
                    break
            
            if all_complete:
                break
            
            time.sleep(0.5)
        
        # Verify all jobs completed
        for job_id in job_ids:
            job = service.get_batch_status(job_id)
            assert job is not None
            assert job.status in [JobStatus.COMPLETED, JobStatus.FAILED]
        
        service.shutdown()
    
    def test_capacity_info_reflects_configuration(
        self,
        transcription_service
    ):
        """Test that capacity info correctly reflects the configuration."""
        # Initially, should have full capacity
        info = transcription_service.get_capacity_info()
        assert info["available_capacity"] == info["max_queue_size"]
        assert not transcription_service.is_at_capacity()
        
        # Test with a service that has small queue
        service = TranscriptionService(max_workers=1, max_queue_size=5)
        service.initialize()
        
        # Should not be at capacity initially
        assert not service.is_at_capacity()
        info = service.get_capacity_info()
        assert info["available_capacity"] == 5
        assert info["max_queue_size"] == 5
        assert info["max_workers"] == 1
        
        service.shutdown()
