"""
Unit tests for WebSocket streaming transcription endpoint.

This module tests the WebSocket endpoint for real-time streaming transcription,
including connection establishment, bidirectional communication, partial results,
and error handling.
"""

import pytest
import json
import time
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock

from app.main import app
from app.transcription_service import TranscriptionService
from app.whisper_engine import WhisperEngine
from app.audio_processor import AudioProcessor


@pytest.fixture
def mock_whisper_engine():
    """Create a mock WhisperEngine for testing."""
    engine = Mock(spec=WhisperEngine)
    engine.is_ready.return_value = True
    engine.model_size = "small"
    engine.transcribe_stream.return_value = None  # Default: no partial result
    engine.finalize_stream.return_value = ""  # Default: empty final result
    engine.clear_buffer.return_value = None
    engine.get_buffer_size.return_value = 0
    return engine


@pytest.fixture
def mock_audio_processor():
    """Create a mock AudioProcessor for testing."""
    processor = Mock(spec=AudioProcessor)
    return processor


@pytest.fixture
def mock_transcription_service(mock_whisper_engine, mock_audio_processor):
    """Create a mock TranscriptionService for testing."""
    service = TranscriptionService(
        audio_processor=mock_audio_processor,
        whisper_engine=mock_whisper_engine
    )
    return service


@pytest.fixture
def client(mock_transcription_service):
    """Create a test client with mocked transcription service."""
    with patch('app.main.transcription_service', mock_transcription_service):
        with TestClient(app) as test_client:
            yield test_client


class TestWebSocketConnection:
    """Test WebSocket connection establishment and lifecycle."""
    
    def test_websocket_connection_establishment(self, client):
        """
        Test that WebSocket connection can be established.
        
        Validates: Requirement 3.1 - Establish bidirectional communication channel
        """
        with client.websocket_connect("/api/v1/transcribe/stream") as websocket:
            # Connection should be established successfully
            assert websocket is not None
            
            # Close the connection
            websocket.close()
    
    def test_websocket_service_unavailable(self):
        """
        Test WebSocket connection when service is not available.
        
        Validates: Requirement 3.5 - Error handling with connection stability
        """
        with patch('app.main.transcription_service', None):
            with TestClient(app) as test_client:
                with test_client.websocket_connect("/api/v1/transcribe/stream") as websocket:
                    # Should receive error message
                    data = websocket.receive_text()
                    message = json.loads(data)
                    
                    assert message["type"] == "error"
                    assert "not available" in message["text"].lower()
                    assert "timestamp" in message
    
    def test_websocket_service_not_ready(self, mock_transcription_service):
        """
        Test WebSocket connection when service is not ready.
        
        Validates: Requirement 3.5 - Error handling during initialization
        """
        # Mock service as not ready
        mock_transcription_service.is_ready = Mock(return_value=False)
        mock_transcription_service.initialize = Mock(side_effect=RuntimeError("Model loading failed"))
        
        with patch('app.main.transcription_service', mock_transcription_service):
            with TestClient(app) as test_client:
                with test_client.websocket_connect("/api/v1/transcribe/stream") as websocket:
                    # Should receive error message
                    data = websocket.receive_text()
                    message = json.loads(data)
                    
                    assert message["type"] == "error"
                    assert "initializing" in message["text"].lower() or "retry" in message["text"].lower()


class TestWebSocketStreaming:
    """Test WebSocket streaming transcription functionality."""
    
    def test_send_audio_chunk_no_partial_result(self, client, mock_transcription_service):
        """
        Test sending audio chunk when buffer threshold not reached.
        
        Validates: Requirement 3.2 - Process audio data incrementally
        """
        # Mock: no partial result yet (buffer not full)
        mock_transcription_service.transcribe_stream_chunk = AsyncMock(return_value=None)
        mock_transcription_service.finalize_stream = AsyncMock(return_value="")
        
        with client.websocket_connect("/api/v1/transcribe/stream") as websocket:
            # Send audio chunk
            audio_chunk = b"fake_audio_data_chunk_1"
            websocket.send_bytes(audio_chunk)
            
            # Should not receive partial result (buffer not full)
            # Close connection to trigger finalization
            websocket.close()
            
            # Should receive final message
            data = websocket.receive_text()
            message = json.loads(data)
            assert message["type"] == "final"
    
    def test_send_audio_chunk_with_partial_result(self, client, mock_transcription_service):
        """
        Test sending audio chunk and receiving partial transcription.
        
        Validates: Requirement 3.3 - Return partial transcription segments
        """
        # Mock: partial result available
        mock_transcription_service.transcribe_stream_chunk = AsyncMock(return_value="سلام")
        mock_transcription_service.finalize_stream = AsyncMock(return_value="")
        
        with client.websocket_connect("/api/v1/transcribe/stream") as websocket:
            # Send audio chunk
            audio_chunk = b"fake_audio_data_chunk_large" * 1000
            websocket.send_bytes(audio_chunk)
            
            # Should receive partial result
            data = websocket.receive_text()
            message = json.loads(data)
            
            assert message["type"] == "partial"
            assert message["text"] == "سلام"
            assert "timestamp" in message
            assert isinstance(message["timestamp"], (int, float))
    
    def test_multiple_audio_chunks_with_partial_results(self, client, mock_transcription_service):
        """
        Test sending multiple audio chunks and receiving multiple partial results.
        
        Validates: Requirement 3.2, 3.3 - Incremental processing with partial results
        """
        # Mock: different partial results for each chunk
        partial_results = ["سلام", "دنیا", "خوبی"]
        mock_transcription_service.transcribe_stream_chunk = AsyncMock(
            side_effect=partial_results
        )
        mock_transcription_service.finalize_stream = AsyncMock(return_value="")
        
        with client.websocket_connect("/api/v1/transcribe/stream") as websocket:
            received_messages = []
            
            # Send multiple chunks
            for i in range(3):
                audio_chunk = f"fake_audio_chunk_{i}".encode() * 1000
                websocket.send_bytes(audio_chunk)
                
                # Receive partial result
                data = websocket.receive_text()
                message = json.loads(data)
                received_messages.append(message)
            
            # Verify all partial results received
            assert len(received_messages) == 3
            for i, msg in enumerate(received_messages):
                assert msg["type"] == "partial"
                assert msg["text"] == partial_results[i]


class TestWebSocketFinalization:
    """Test WebSocket connection finalization and cleanup."""
    
    def test_connection_close_with_final_result(self, client, mock_transcription_service):
        """
        Test that closing connection returns final transcription.
        
        Validates: Requirement 3.4 - Finalize and return remaining content on close
        """
        # Mock: final result available
        mock_transcription_service.transcribe_stream_chunk = AsyncMock(return_value=None)
        mock_transcription_service.finalize_stream = AsyncMock(return_value="نهایی")
        
        with client.websocket_connect("/api/v1/transcribe/stream") as websocket:
            # Send a chunk
            websocket.send_bytes(b"audio_data")
            
            # Close connection
            websocket.close()
            
            # Should receive final message
            data = websocket.receive_text()
            message = json.loads(data)
            
            assert message["type"] == "final"
            assert message["text"] == "نهایی"
            assert "timestamp" in message
    
    def test_connection_close_with_empty_final_result(self, client, mock_transcription_service):
        """
        Test that closing connection with empty buffer returns empty final result.
        
        Validates: Requirement 3.4 - Handle empty buffer on close
        """
        # Mock: no final result (empty buffer)
        mock_transcription_service.transcribe_stream_chunk = AsyncMock(return_value=None)
        mock_transcription_service.finalize_stream = AsyncMock(return_value="")
        
        with client.websocket_connect("/api/v1/transcribe/stream") as websocket:
            # Close connection immediately
            websocket.close()
            
            # Should receive empty final message
            data = websocket.receive_text()
            message = json.loads(data)
            
            assert message["type"] == "final"
            assert message["text"] == ""
    
    def test_buffer_cleared_on_connection(self, client, mock_transcription_service):
        """
        Test that streaming buffer is cleared when connection is established.
        
        Validates: Clean state for each new connection
        """
        with client.websocket_connect("/api/v1/transcribe/stream") as websocket:
            # Buffer should be cleared on connection
            mock_transcription_service.clear_stream_buffer.assert_called()
            
            websocket.close()


class TestWebSocketErrorHandling:
    """Test WebSocket error handling and stability."""
    
    def test_audio_processing_error_maintains_connection(self, client, mock_transcription_service):
        """
        Test that processing errors are reported but connection is maintained.
        
        Validates: Requirement 3.5 - Notify client and maintain connection stability
        """
        # Mock: processing error on first chunk, success on second
        mock_transcription_service.transcribe_stream_chunk = AsyncMock(
            side_effect=[ValueError("Buffer size exceeded"), "success"]
        )
        mock_transcription_service.finalize_stream = AsyncMock(return_value="")
        
        with client.websocket_connect("/api/v1/transcribe/stream") as websocket:
            # Send first chunk (will error)
            websocket.send_bytes(b"bad_chunk")
            
            # Should receive error message
            data = websocket.receive_text()
            message = json.loads(data)
            assert message["type"] == "error"
            assert "error" in message["text"].lower()
            
            # Connection should still be open - send another chunk
            websocket.send_bytes(b"good_chunk")
            
            # Should receive success result
            data = websocket.receive_text()
            message = json.loads(data)
            assert message["type"] == "partial"
            assert message["text"] == "success"
    
    def test_transcription_error_maintains_connection(self, client, mock_transcription_service):
        """
        Test that transcription errors are reported but connection is maintained.
        
        Validates: Requirement 3.5 - Error handling with connection stability
        """
        # Mock: transcription error on first chunk, success on second
        mock_transcription_service.transcribe_stream_chunk = AsyncMock(
            side_effect=[RuntimeError("Transcription failed"), "recovered"]
        )
        mock_transcription_service.finalize_stream = AsyncMock(return_value="")
        
        with client.websocket_connect("/api/v1/transcribe/stream") as websocket:
            # Send first chunk (will error)
            websocket.send_bytes(b"chunk1")
            
            # Should receive error message
            data = websocket.receive_text()
            message = json.loads(data)
            assert message["type"] == "error"
            assert "transcription error" in message["text"].lower()
            
            # Connection should still be open
            websocket.send_bytes(b"chunk2")
            
            # Should receive success result
            data = websocket.receive_text()
            message = json.loads(data)
            assert message["type"] == "partial"
            assert message["text"] == "recovered"
    
    def test_finalization_error_reported(self, client, mock_transcription_service):
        """
        Test that finalization errors are reported to client.
        
        Validates: Requirement 3.5 - Error notification
        """
        # Mock: finalization error
        mock_transcription_service.transcribe_stream_chunk = AsyncMock(return_value=None)
        mock_transcription_service.finalize_stream = AsyncMock(
            side_effect=RuntimeError("Finalization failed")
        )
        
        with client.websocket_connect("/api/v1/transcribe/stream") as websocket:
            # Send a chunk
            websocket.send_bytes(b"audio_data")
            
            # Close connection
            websocket.close()
            
            # Should receive error message
            data = websocket.receive_text()
            message = json.loads(data)
            
            assert message["type"] == "error"
            assert "finalization error" in message["text"].lower()
    
    def test_empty_audio_chunk_skipped(self, client, mock_transcription_service):
        """
        Test that empty audio chunks are skipped without error.
        
        Validates: Robust handling of edge cases
        """
        # Mock: normal processing
        mock_transcription_service.transcribe_stream_chunk = AsyncMock(return_value="result")
        mock_transcription_service.finalize_stream = AsyncMock(return_value="")
        
        with client.websocket_connect("/api/v1/transcribe/stream") as websocket:
            # Send empty chunk (should be skipped)
            websocket.send_bytes(b"")
            
            # Send valid chunk
            websocket.send_bytes(b"valid_audio_data")
            
            # Should receive result from valid chunk only
            data = websocket.receive_text()
            message = json.loads(data)
            
            assert message["type"] == "partial"
            assert message["text"] == "result"
            
            # transcribe_stream_chunk should be called only once (for valid chunk)
            assert mock_transcription_service.transcribe_stream_chunk.call_count == 1


class TestWebSocketMessageFormat:
    """Test WebSocket message format compliance."""
    
    def test_partial_message_format(self, client, mock_transcription_service):
        """
        Test that partial messages have correct format.
        
        Validates: Consistent message structure
        """
        mock_transcription_service.transcribe_stream_chunk = AsyncMock(return_value="test")
        mock_transcription_service.finalize_stream = AsyncMock(return_value="")
        
        with client.websocket_connect("/api/v1/transcribe/stream") as websocket:
            websocket.send_bytes(b"audio_data")
            
            data = websocket.receive_text()
            message = json.loads(data)
            
            # Verify message structure
            assert "type" in message
            assert "text" in message
            assert "timestamp" in message
            assert message["type"] == "partial"
            assert isinstance(message["text"], str)
            assert isinstance(message["timestamp"], (int, float))
    
    def test_final_message_format(self, client, mock_transcription_service):
        """
        Test that final messages have correct format.
        
        Validates: Consistent message structure
        """
        mock_transcription_service.transcribe_stream_chunk = AsyncMock(return_value=None)
        mock_transcription_service.finalize_stream = AsyncMock(return_value="final_text")
        
        with client.websocket_connect("/api/v1/transcribe/stream") as websocket:
            websocket.close()
            
            data = websocket.receive_text()
            message = json.loads(data)
            
            # Verify message structure
            assert "type" in message
            assert "text" in message
            assert "timestamp" in message
            assert message["type"] == "final"
            assert isinstance(message["text"], str)
            assert isinstance(message["timestamp"], (int, float))
    
    def test_error_message_format(self, client, mock_transcription_service):
        """
        Test that error messages have correct format.
        
        Validates: Consistent error message structure
        """
        mock_transcription_service.transcribe_stream_chunk = AsyncMock(
            side_effect=ValueError("Test error")
        )
        mock_transcription_service.finalize_stream = AsyncMock(return_value="")
        
        with client.websocket_connect("/api/v1/transcribe/stream") as websocket:
            websocket.send_bytes(b"audio_data")
            
            data = websocket.receive_text()
            message = json.loads(data)
            
            # Verify message structure
            assert "type" in message
            assert "text" in message
            assert "timestamp" in message
            assert message["type"] == "error"
            assert isinstance(message["text"], str)
            assert isinstance(message["timestamp"], (int, float))
            assert "error" in message["text"].lower()


class TestWebSocketIntegration:
    """Integration tests for complete WebSocket workflows."""
    
    def test_complete_streaming_workflow(self, client, mock_transcription_service):
        """
        Test complete streaming workflow from connection to finalization.
        
        Validates: Requirements 3.1, 3.2, 3.3, 3.4 - Complete streaming workflow
        """
        # Mock: realistic streaming scenario
        partial_results = ["سلام", "دنیا", None, "خوبی"]  # None = buffer not full
        mock_transcription_service.transcribe_stream_chunk = AsyncMock(
            side_effect=partial_results
        )
        mock_transcription_service.finalize_stream = AsyncMock(return_value="پایان")
        
        with client.websocket_connect("/api/v1/transcribe/stream") as websocket:
            received_messages = []
            
            # Send multiple chunks
            for i in range(4):
                audio_chunk = f"chunk_{i}".encode() * 100
                websocket.send_bytes(audio_chunk)
                
                # Try to receive message (may not always have one)
                try:
                    data = websocket.receive_text()
                    message = json.loads(data)
                    if message["type"] == "partial":
                        received_messages.append(message)
                except:
                    pass
            
            # Close connection
            websocket.close()
            
            # Receive final message
            data = websocket.receive_text()
            final_message = json.loads(data)
            
            # Verify workflow
            assert len(received_messages) >= 2  # At least some partial results
            assert all(msg["type"] == "partial" for msg in received_messages)
            assert final_message["type"] == "final"
            assert final_message["text"] == "پایان"
            
            # Verify buffer was cleared
            mock_transcription_service.clear_stream_buffer.assert_called()
