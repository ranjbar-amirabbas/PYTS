"""
Unit tests for batch transcription API endpoints.

Tests the POST /api/v1/transcribe/batch and GET /api/v1/transcribe/batch/{job_id}
endpoints, including request validation, file size limits, and error handling.
"""

import pytest
import io
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.models import Job, JobStatus
from app.audio_processor import UnsupportedFormatError


client = TestClient(app)


class TestBatchTranscriptionUpload:
    """Test POST /api/v1/transcribe/batch endpoint."""
    
    @patch('app.main.transcription_service')
    def test_upload_valid_wav_file(self, mock_service):
        """Test uploading a valid WAV file returns job ID."""
        # Mock service
        mock_service.is_ready.return_value = True
        mock_service.is_at_capacity.return_value = False
        mock_service.transcribe_batch.return_value = "test-job-id-123"
        
        # Create a small WAV file
        audio_data = b"RIFF" + b"\x00" * 100  # Minimal WAV header
        files = {"audio_file": ("test.wav", io.BytesIO(audio_data), "audio/wav")}
        
        response = client.post("/api/v1/transcribe/batch", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["job_id"] == "test-job-id-123"
        assert data["status"] == "pending"
    
    @patch('app.main.transcription_service')
    def test_upload_valid_mp3_file(self, mock_service):
        """Test uploading a valid MP3 file returns job ID."""
        mock_service.is_ready.return_value = True
        mock_service.transcribe_batch.return_value = "test-job-id-456"
        
        audio_data = b"\xff\xfb" + b"\x00" * 100  # MP3 header
        files = {"audio_file": ("test.mp3", io.BytesIO(audio_data), "audio/mpeg")}
        
        response = client.post("/api/v1/transcribe/batch", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test-job-id-456"
        assert data["status"] == "pending"
    
    @patch('app.main.transcription_service')
    def test_upload_valid_ogg_file(self, mock_service):
        """Test uploading a valid OGG file returns job ID."""
        mock_service.is_ready.return_value = True
        mock_service.transcribe_batch.return_value = "test-job-id-789"
        
        audio_data = b"OggS" + b"\x00" * 100  # OGG header
        files = {"audio_file": ("test.ogg", io.BytesIO(audio_data), "audio/ogg")}
        
        response = client.post("/api/v1/transcribe/batch", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test-job-id-789"
    
    @patch('app.main.transcription_service')
    def test_upload_valid_m4a_file(self, mock_service):
        """Test uploading a valid M4A file returns job ID."""
        mock_service.is_ready.return_value = True
        mock_service.transcribe_batch.return_value = "test-job-id-m4a"
        
        audio_data = b"\x00\x00\x00\x20ftyp" + b"\x00" * 100  # M4A header
        files = {"audio_file": ("test.m4a", io.BytesIO(audio_data), "audio/mp4")}
        
        response = client.post("/api/v1/transcribe/batch", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test-job-id-m4a"
    
    @patch('app.main.transcription_service')
    def test_upload_unsupported_format_returns_415(self, mock_service):
        """Test uploading unsupported format returns 415 error."""
        mock_service.is_ready.return_value = True
        
        audio_data = b"fake audio data"
        files = {"audio_file": ("test.txt", io.BytesIO(audio_data), "text/plain")}
        
        response = client.post("/api/v1/transcribe/batch", files=files)
        
        assert response.status_code == 415
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
        assert data["detail"]["error"]["code"] == "UNSUPPORTED_FORMAT"
        assert "Supported formats" in data["detail"]["error"]["message"]
    
    @patch('app.main.transcription_service')
    def test_upload_without_file_returns_422(self, mock_service):
        """Test uploading without file returns validation error."""
        mock_service.is_ready.return_value = True
        
        response = client.post("/api/v1/transcribe/batch")
        
        # FastAPI returns 400 for validation errors with our custom handler
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "VALIDATION_ERROR"
    
    @patch('app.main.transcription_service')
    def test_upload_exceeds_size_limit_returns_413(self, mock_service):
        """Test uploading file exceeding size limit returns 413 error."""
        mock_service.is_ready.return_value = True
        
        # Create a file larger than MAX_FILE_SIZE_BYTES (500 MB)
        # We'll simulate this by creating a generator that yields chunks
        def large_file_generator():
            # Yield chunks totaling > 500 MB
            chunk_size = 1024 * 1024  # 1 MB
            for _ in range(501):  # 501 MB
                yield b"\x00" * chunk_size
        
        # Note: This test is tricky because we need to actually stream the data
        # For now, we'll test with a smaller limit by mocking
        with patch('app.main.MAX_FILE_SIZE_BYTES', 1024):  # 1 KB limit
            audio_data = b"\x00" * 2048  # 2 KB file
            files = {"audio_file": ("large.wav", io.BytesIO(audio_data), "audio/wav")}
            
            response = client.post("/api/v1/transcribe/batch", files=files)
            
            assert response.status_code == 413
            data = response.json()
            assert "detail" in data
            assert "error" in data["detail"]
            assert data["detail"]["error"]["code"] == "FILE_TOO_LARGE"
    
    @patch('app.main.transcription_service')
    def test_upload_when_service_not_ready_initializes_model(self, mock_service):
        """Test that model is initialized on first request if not ready."""
        mock_service.is_ready.return_value = False
        mock_service.initialize = Mock()
        
        # After initialize is called, is_ready should return True
        def side_effect():
            mock_service.is_ready.return_value = True
        
        mock_service.initialize.side_effect = side_effect
        mock_service.transcribe_batch.return_value = "test-job-id"
        
        audio_data = b"RIFF" + b"\x00" * 100
        files = {"audio_file": ("test.wav", io.BytesIO(audio_data), "audio/wav")}
        
        response = client.post("/api/v1/transcribe/batch", files=files)
        
        assert response.status_code == 200
        mock_service.initialize.assert_called_once()
    
    @patch('app.main.transcription_service')
    def test_upload_when_initialization_fails_returns_503(self, mock_service):
        """Test that initialization failure returns 503 error."""
        mock_service.is_ready.return_value = False
        mock_service.initialize.side_effect = RuntimeError("Model loading failed")
        
        audio_data = b"RIFF" + b"\x00" * 100
        files = {"audio_file": ("test.wav", io.BytesIO(audio_data), "audio/wav")}
        
        response = client.post("/api/v1/transcribe/batch", files=files)
        
        assert response.status_code == 503
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
        assert data["detail"]["error"]["code"] == "SERVICE_UNAVAILABLE"
    
    @patch('app.main.transcription_service')
    def test_upload_with_format_validation_error_returns_415(self, mock_service):
        """Test that format validation error returns 415."""
        mock_service.is_ready.return_value = True
        mock_service.transcribe_batch.side_effect = UnsupportedFormatError(
            "Audio format not supported"
        )
        
        audio_data = b"fake data"
        files = {"audio_file": ("test.wav", io.BytesIO(audio_data), "audio/wav")}
        
        response = client.post("/api/v1/transcribe/batch", files=files)
        
        assert response.status_code == 415
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
        assert data["detail"]["error"]["code"] == "UNSUPPORTED_FORMAT"
    
    @patch('app.main.transcription_service')
    def test_upload_with_file_not_found_error_returns_400(self, mock_service):
        """Test that FileNotFoundError returns 400."""
        mock_service.is_ready.return_value = True
        mock_service.transcribe_batch.side_effect = FileNotFoundError(
            "Audio file not found"
        )
        
        audio_data = b"RIFF" + b"\x00" * 100
        files = {"audio_file": ("test.wav", io.BytesIO(audio_data), "audio/wav")}
        
        response = client.post("/api/v1/transcribe/batch", files=files)
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
        assert data["detail"]["error"]["code"] == "FILE_NOT_FOUND"
    
    @patch('app.main.transcription_service', None)
    def test_upload_when_service_unavailable_returns_503(self):
        """Test that unavailable service returns 503."""
        audio_data = b"RIFF" + b"\x00" * 100
        files = {"audio_file": ("test.wav", io.BytesIO(audio_data), "audio/wav")}
        
        response = client.post("/api/v1/transcribe/batch", files=files)
        
        assert response.status_code == 503
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
        assert data["detail"]["error"]["code"] == "SERVICE_UNAVAILABLE"


class TestBatchTranscriptionStatus:
    """Test GET /api/v1/transcribe/batch/{job_id} endpoint."""
    
    @patch('app.main.transcription_service')
    def test_get_status_pending_job(self, mock_service):
        """Test getting status of a pending job."""
        job = Job(
            job_id="test-job-123",
            audio_file_path="/tmp/test.wav",
            status=JobStatus.PENDING
        )
        mock_service.get_batch_status.return_value = job
        
        response = client.get("/api/v1/transcribe/batch/test-job-123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test-job-123"
        assert data["status"] == "pending"
        assert data["transcription"] is None
        assert data["error"] is None
    
    @patch('app.main.transcription_service')
    def test_get_status_processing_job(self, mock_service):
        """Test getting status of a processing job."""
        job = Job(
            job_id="test-job-456",
            audio_file_path="/tmp/test.wav",
            status=JobStatus.PROCESSING
        )
        mock_service.get_batch_status.return_value = job
        
        response = client.get("/api/v1/transcribe/batch/test-job-456")
        
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test-job-456"
        assert data["status"] == "processing"
        assert data["transcription"] is None
        assert data["error"] is None
    
    @patch('app.main.transcription_service')
    def test_get_status_completed_job(self, mock_service):
        """Test getting status of a completed job with transcription."""
        job = Job(
            job_id="test-job-789",
            audio_file_path="/tmp/test.wav",
            status=JobStatus.COMPLETED,
            transcription="سلام دنیا"
        )
        mock_service.get_batch_status.return_value = job
        
        response = client.get("/api/v1/transcribe/batch/test-job-789")
        
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test-job-789"
        assert data["status"] == "completed"
        assert data["transcription"] == "سلام دنیا"
        assert data["error"] is None
    
    @patch('app.main.transcription_service')
    def test_get_status_failed_job(self, mock_service):
        """Test getting status of a failed job with error message."""
        job = Job(
            job_id="test-job-fail",
            audio_file_path="/tmp/test.wav",
            status=JobStatus.FAILED,
            error_message="Audio file is corrupted"
        )
        mock_service.get_batch_status.return_value = job
        
        response = client.get("/api/v1/transcribe/batch/test-job-fail")
        
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test-job-fail"
        assert data["status"] == "failed"
        assert data["transcription"] is None
        assert data["error"] == "Audio file is corrupted"
    
    @patch('app.main.transcription_service')
    def test_get_status_nonexistent_job_returns_404(self, mock_service):
        """Test getting status of non-existent job returns 404."""
        mock_service.get_batch_status.return_value = None
        
        response = client.get("/api/v1/transcribe/batch/nonexistent-job")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
        assert data["detail"]["error"]["code"] == "JOB_NOT_FOUND"
        assert "nonexistent-job" in data["detail"]["error"]["message"]
    
    @patch('app.main.transcription_service', None)
    def test_get_status_when_service_unavailable_returns_503(self):
        """Test that unavailable service returns 503."""
        response = client.get("/api/v1/transcribe/batch/test-job-123")
        
        assert response.status_code == 503
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
        assert data["detail"]["error"]["code"] == "SERVICE_UNAVAILABLE"


class TestBatchEndpointIntegration:
    """Integration tests for batch transcription workflow."""
    
    @patch('app.main.transcription_service')
    def test_full_batch_workflow(self, mock_service):
        """Test complete workflow: upload -> check status -> get result."""
        # Setup mocks
        mock_service.is_ready.return_value = True
        mock_service.transcribe_batch.return_value = "workflow-job-123"
        
        # Step 1: Upload file
        audio_data = b"RIFF" + b"\x00" * 100
        files = {"audio_file": ("test.wav", io.BytesIO(audio_data), "audio/wav")}
        
        upload_response = client.post("/api/v1/transcribe/batch", files=files)
        assert upload_response.status_code == 200
        job_id = upload_response.json()["job_id"]
        assert job_id == "workflow-job-123"
        
        # Step 2: Check status (pending)
        pending_job = Job(
            job_id=job_id,
            audio_file_path="/tmp/test.wav",
            status=JobStatus.PENDING
        )
        mock_service.get_batch_status.return_value = pending_job
        
        status_response = client.get(f"/api/v1/transcribe/batch/{job_id}")
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "pending"
        
        # Step 3: Check status (completed)
        completed_job = Job(
            job_id=job_id,
            audio_file_path="/tmp/test.wav",
            status=JobStatus.COMPLETED,
            transcription="این یک تست است"
        )
        mock_service.get_batch_status.return_value = completed_job
        
        final_response = client.get(f"/api/v1/transcribe/batch/{job_id}")
        assert final_response.status_code == 200
        data = final_response.json()
        assert data["status"] == "completed"
        assert data["transcription"] == "این یک تست است"
    
    @patch('app.main.transcription_service')
    def test_error_response_format_consistency(self, mock_service):
        """Test that all error responses follow consistent format."""
        # Test 415 error format
        mock_service.is_ready.return_value = True
        audio_data = b"fake"
        files = {"audio_file": ("test.txt", io.BytesIO(audio_data), "text/plain")}
        
        response = client.post("/api/v1/transcribe/batch", files=files)
        assert response.status_code == 415
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
        assert "code" in data["detail"]["error"]
        assert "message" in data["detail"]["error"]
        assert "details" in data["detail"]["error"]
        
        # Test 404 error format
        mock_service.get_batch_status.return_value = None
        response = client.get("/api/v1/transcribe/batch/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
        assert "code" in data["detail"]["error"]
        assert "message" in data["detail"]["error"]
        assert "details" in data["detail"]["error"]


class TestRequestValidation:
    """Test request validation and edge cases."""
    
    @patch('app.main.transcription_service')
    def test_empty_file_upload(self, mock_service):
        """Test uploading an empty file."""
        mock_service.is_ready.return_value = True
        mock_service.transcribe_batch.return_value = "empty-job"
        
        audio_data = b""  # Empty file
        files = {"audio_file": ("empty.wav", io.BytesIO(audio_data), "audio/wav")}
        
        response = client.post("/api/v1/transcribe/batch", files=files)
        
        # Should accept empty file (validation happens in audio processor)
        assert response.status_code == 200
    
    @patch('app.main.transcription_service')
    def test_filename_with_special_characters(self, mock_service):
        """Test uploading file with special characters in filename."""
        mock_service.is_ready.return_value = True
        mock_service.transcribe_batch.return_value = "special-job"
        
        audio_data = b"RIFF" + b"\x00" * 100
        files = {
            "audio_file": (
                "test file (1) [copy].wav",
                io.BytesIO(audio_data),
                "audio/wav"
            )
        }
        
        response = client.post("/api/v1/transcribe/batch", files=files)
        assert response.status_code == 200
    
    @patch('app.main.transcription_service')
    def test_job_id_with_special_characters(self, mock_service):
        """Test getting status with various job ID formats."""
        job = Job(
            job_id="550e8400-e29b-41d4-a716-446655440000",
            audio_file_path="/tmp/test.wav",
            status=JobStatus.PENDING
        )
        mock_service.get_batch_status.return_value = job
        
        # UUID format
        response = client.get("/api/v1/transcribe/batch/550e8400-e29b-41d4-a716-446655440000")
        assert response.status_code == 200
        
        # Simple alphanumeric
        job.job_id = "abc123"
        response = client.get("/api/v1/transcribe/batch/abc123")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
