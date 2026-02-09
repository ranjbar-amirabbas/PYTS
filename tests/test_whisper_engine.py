"""
Unit tests for the WhisperEngine class.

Tests model initialization, loading, and readiness checks.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from app.whisper_engine import WhisperEngine, ModelNotReadyError


class TestWhisperEngineInitialization:
    """Tests for WhisperEngine initialization."""
    
    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        engine = WhisperEngine()
        
        assert engine.model_size == "medium"
        assert engine.language == "fa"
        assert engine.device is None
        assert not engine.is_ready()
    
    def test_init_with_custom_parameters(self):
        """Test initialization with custom parameters."""
        engine = WhisperEngine(
            model_size="small",
            language="fa",
            device="cpu"
        )
        
        assert engine.model_size == "small"
        assert engine.language == "fa"
        assert engine.device == "cpu"
        assert not engine.is_ready()
    
    def test_init_with_different_model_sizes(self):
        """Test initialization with different model sizes."""
        model_sizes = ["tiny", "base", "small", "medium", "large"]
        
        for size in model_sizes:
            engine = WhisperEngine(model_size=size)
            assert engine.model_size == size


class TestWhisperEngineModelLoading:
    """Tests for model loading functionality."""
    
    @patch('app.whisper_engine.whisper.load_model')
    def test_load_model_success(self, mock_load_model):
        """Test successful model loading."""
        # Mock the Whisper model
        mock_model = Mock()
        mock_model.device = "cpu"
        mock_load_model.return_value = mock_model
        
        engine = WhisperEngine(model_size="small")
        assert not engine.is_ready()
        
        engine.load_model()
        
        assert engine.is_ready()
        mock_load_model.assert_called_once_with(name="small", device=None)
    
    @patch('app.whisper_engine.whisper.load_model')
    def test_load_model_with_device(self, mock_load_model):
        """Test model loading with specific device."""
        mock_model = Mock()
        mock_model.device = "cuda"
        mock_load_model.return_value = mock_model
        
        engine = WhisperEngine(model_size="medium", device="cuda")
        engine.load_model()
        
        assert engine.is_ready()
        mock_load_model.assert_called_once_with(name="medium", device="cuda")
    
    @patch('app.whisper_engine.whisper.load_model')
    def test_load_model_failure(self, mock_load_model):
        """Test model loading failure."""
        mock_load_model.side_effect = Exception("Model download failed")
        
        engine = WhisperEngine()
        
        with pytest.raises(RuntimeError, match="Failed to load Whisper model"):
            engine.load_model()
        
        assert not engine.is_ready()


class TestWhisperEngineReadinessCheck:
    """Tests for model readiness checks."""
    
    def test_is_ready_before_loading(self):
        """Test is_ready returns False before model is loaded."""
        engine = WhisperEngine()
        assert not engine.is_ready()
    
    @patch('app.whisper_engine.whisper.load_model')
    def test_is_ready_after_loading(self, mock_load_model):
        """Test is_ready returns True after successful model loading."""
        mock_model = Mock()
        mock_model.device = "cpu"
        mock_load_model.return_value = mock_model
        
        engine = WhisperEngine()
        engine.load_model()
        
        assert engine.is_ready()
    
    @patch('app.whisper_engine.whisper.load_model')
    def test_is_ready_after_failed_loading(self, mock_load_model):
        """Test is_ready returns False after failed model loading."""
        mock_load_model.side_effect = Exception("Load failed")
        
        engine = WhisperEngine()
        
        try:
            engine.load_model()
        except RuntimeError:
            pass
        
        assert not engine.is_ready()


class TestWhisperEngineModelInfo:
    """Tests for get_model_info method."""
    
    def test_get_model_info_before_loading(self):
        """Test get_model_info before model is loaded."""
        engine = WhisperEngine(model_size="small", language="fa")
        info = engine.get_model_info()
        
        assert info["model_size"] == "small"
        assert info["language"] == "fa"
        assert info["device"] is None
        assert info["is_ready"] is False
    
    @patch('app.whisper_engine.whisper.load_model')
    def test_get_model_info_after_loading(self, mock_load_model):
        """Test get_model_info after model is loaded."""
        mock_model = Mock()
        mock_model.device = "cpu"
        mock_load_model.return_value = mock_model
        
        engine = WhisperEngine(model_size="medium", language="fa")
        engine.load_model()
        info = engine.get_model_info()
        
        assert info["model_size"] == "medium"
        assert info["language"] == "fa"
        assert info["device"] == "cpu"
        assert info["is_ready"] is True


class TestWhisperEngineTranscription:
    """Tests for transcription functionality."""
    
    def test_transcribe_without_loading_model(self, tmp_path):
        """Test transcribe raises error when model is not loaded."""
        engine = WhisperEngine()
        
        # Create a dummy audio file
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"dummy audio data")
        
        with pytest.raises(ModelNotReadyError, match="Whisper model is not loaded"):
            engine.transcribe(str(audio_file))
    
    @patch('app.whisper_engine.whisper.load_model')
    def test_transcribe_with_nonexistent_file(self, mock_load_model):
        """Test transcribe raises error for nonexistent file."""
        mock_model = Mock()
        mock_model.device = "cpu"
        mock_load_model.return_value = mock_model
        
        engine = WhisperEngine()
        engine.load_model()
        
        with pytest.raises(FileNotFoundError, match="Audio file not found"):
            engine.transcribe("/nonexistent/file.wav")
    
    @patch('app.whisper_engine.whisper.load_model')
    def test_transcribe_success(self, mock_load_model, tmp_path):
        """Test successful transcription."""
        # Mock the model and its transcribe method
        mock_model = Mock()
        mock_model.device = "cpu"
        mock_model.transcribe.return_value = {
            "text": "سلام دنیا",  # "Hello World" in Persian
            "segments": []
        }
        mock_load_model.return_value = mock_model
        
        # Create a dummy audio file
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"dummy audio data")
        
        engine = WhisperEngine()
        engine.load_model()
        
        result = engine.transcribe(str(audio_file))
        
        assert result == "سلام دنیا"
        mock_model.transcribe.assert_called_once()
        
        # Verify the call arguments
        call_args = mock_model.transcribe.call_args
        assert call_args[1]["language"] == "fa"
        assert call_args[1]["task"] == "transcribe"
        assert call_args[1]["verbose"] is False
    
    @patch('app.whisper_engine.whisper.load_model')
    def test_transcribe_with_whitespace(self, mock_load_model, tmp_path):
        """Test transcription strips whitespace from result."""
        mock_model = Mock()
        mock_model.device = "cpu"
        mock_model.transcribe.return_value = {
            "text": "  سلام دنیا  ",  # Text with leading/trailing whitespace
            "segments": []
        }
        mock_load_model.return_value = mock_model
        
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"dummy audio data")
        
        engine = WhisperEngine()
        engine.load_model()
        
        result = engine.transcribe(str(audio_file))
        
        assert result == "سلام دنیا"  # Whitespace should be stripped
    
    @patch('app.whisper_engine.whisper.load_model')
    def test_transcribe_failure(self, mock_load_model, tmp_path):
        """Test transcription failure handling."""
        mock_model = Mock()
        mock_model.device = "cpu"
        mock_model.transcribe.side_effect = Exception("Transcription error")
        mock_load_model.return_value = mock_model
        
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"dummy audio data")
        
        engine = WhisperEngine()
        engine.load_model()
        
        with pytest.raises(RuntimeError, match="Transcription failed"):
            engine.transcribe(str(audio_file))


class TestWhisperEngineChunkTranscription:
    """Tests for chunk transcription (streaming)."""
    
    @patch('app.whisper_engine.whisper.load_model')
    def test_transcribe_chunk(self, mock_load_model, tmp_path):
        """Test chunk transcription."""
        mock_model = Mock()
        mock_model.device = "cpu"
        mock_model.transcribe.return_value = {
            "text": "این یک تست است",  # "This is a test" in Persian
            "segments": []
        }
        mock_load_model.return_value = mock_model
        
        audio_file = tmp_path / "chunk.wav"
        audio_file.write_bytes(b"dummy audio chunk")
        
        engine = WhisperEngine()
        engine.load_model()
        
        result = engine.transcribe_chunk(str(audio_file))
        
        assert result == "این یک تست است"
        mock_model.transcribe.assert_called_once()


class TestWhisperEngineUnload:
    """Tests for model unloading."""
    
    @patch('app.whisper_engine.whisper.load_model')
    def test_unload_model(self, mock_load_model):
        """Test model unloading."""
        mock_model = Mock()
        mock_model.device = "cpu"
        mock_load_model.return_value = mock_model
        
        engine = WhisperEngine()
        engine.load_model()
        
        assert engine.is_ready()
        
        engine.unload_model()
        
        assert not engine.is_ready()
    
    def test_unload_model_when_not_loaded(self):
        """Test unloading when model is not loaded."""
        engine = WhisperEngine()
        
        # Should not raise an error
        engine.unload_model()
        
        assert not engine.is_ready()


class TestWhisperEnginePersianLanguageConfiguration:
    """Tests for Persian language configuration."""
    
    @patch('app.whisper_engine.whisper.load_model')
    def test_persian_language_code(self, mock_load_model, tmp_path):
        """Test that Persian language code 'fa' is used in transcription."""
        mock_model = Mock()
        mock_model.device = "cpu"
        mock_model.transcribe.return_value = {"text": "متن فارسی", "segments": []}
        mock_load_model.return_value = mock_model
        
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"dummy audio")
        
        engine = WhisperEngine(language="fa")
        engine.load_model()
        engine.transcribe(str(audio_file))
        
        # Verify that language="fa" was passed to transcribe
        call_args = mock_model.transcribe.call_args
        assert call_args[1]["language"] == "fa"
    
    def test_default_language_is_persian(self):
        """Test that default language is Persian (fa)."""
        engine = WhisperEngine()
        assert engine.language == "fa"
class TestWhisperEngineStreamingTranscription:
    """Tests for streaming transcription functionality."""

    def test_add_audio_chunk(self):
        """Test adding audio chunks to buffer."""
        engine = WhisperEngine()

        chunk1 = b"audio data 1"
        chunk2 = b"audio data 2"

        engine.add_audio_chunk(chunk1)
        assert engine.get_buffer_size() == len(chunk1)

        engine.add_audio_chunk(chunk2)
        assert engine.get_buffer_size() == len(chunk1) + len(chunk2)

    def test_add_empty_chunk(self):
        """Test adding empty chunk doesn't change buffer."""
        engine = WhisperEngine()

        engine.add_audio_chunk(b"")
        assert engine.get_buffer_size() == 0

    def test_add_chunk_exceeds_buffer_limit(self):
        """Test adding chunk that exceeds buffer limit raises error."""
        engine = WhisperEngine()

        # Create a chunk larger than the max buffer size
        large_chunk = b"x" * (engine._max_buffer_size + 1)

        with pytest.raises(ValueError, match="Stream buffer size would exceed maximum limit"):
            engine.add_audio_chunk(large_chunk)

    def test_clear_buffer(self):
        """Test clearing the buffer."""
        engine = WhisperEngine()

        engine.add_audio_chunk(b"audio data")
        assert engine.get_buffer_size() > 0

        engine.clear_buffer()
        assert engine.get_buffer_size() == 0

    def test_get_buffer_size(self):
        """Test getting buffer size."""
        engine = WhisperEngine()

        assert engine.get_buffer_size() == 0

        chunk = b"test audio data"
        engine.add_audio_chunk(chunk)

        assert engine.get_buffer_size() == len(chunk)

    def test_transcribe_stream_without_loading_model(self):
        """Test transcribe_stream raises error when model is not loaded."""
        engine = WhisperEngine()

        with pytest.raises(ModelNotReadyError, match="Whisper model is not loaded"):
            engine.transcribe_stream(b"audio chunk")

    @patch('app.whisper_engine.whisper.load_model')
    def test_transcribe_stream_buffers_small_chunks(self, mock_load_model):
        """Test that small chunks are buffered without transcription."""
        mock_model = Mock()
        mock_model.device = "cpu"
        mock_load_model.return_value = mock_model

        engine = WhisperEngine()
        engine.load_model()

        # Add a small chunk (below min_chunk_size threshold)
        small_chunk = b"x" * 1024  # 1 KB
        result = engine.transcribe_stream(small_chunk, min_chunk_size=100 * 1024)

        # Should return None (buffered, not transcribed)
        assert result is None
        assert engine.get_buffer_size() == len(small_chunk)

        # Model transcribe should not be called
        mock_model.transcribe.assert_not_called()

    @patch('app.whisper_engine.whisper.load_model')
    def test_transcribe_stream_processes_large_chunks(self, mock_load_model, tmp_path):
        """Test that large chunks trigger transcription."""
        mock_model = Mock()
        mock_model.device = "cpu"
        mock_model.transcribe.return_value = {
            "text": "نسخه جزئی",  # "Partial transcription" in Persian
            "segments": []
        }
        mock_load_model.return_value = mock_model

        engine = WhisperEngine()
        engine.load_model()

        # Add a large chunk (above min_chunk_size threshold)
        large_chunk = b"x" * (150 * 1024)  # 150 KB
        result = engine.transcribe_stream(large_chunk, min_chunk_size=100 * 1024)

        # Should return transcription
        assert result == "نسخه جزئی"

        # Buffer should be cleared after transcription
        assert engine.get_buffer_size() == 0

        # Model transcribe should be called
        mock_model.transcribe.assert_called_once()

    @patch('app.whisper_engine.whisper.load_model')
    def test_transcribe_stream_accumulates_chunks(self, mock_load_model):
        """Test that multiple small chunks accumulate until threshold."""
        mock_model = Mock()
        mock_model.device = "cpu"
        mock_model.transcribe.return_value = {
            "text": "متن تجمعی",  # "Accumulated text" in Persian
            "segments": []
        }
        mock_load_model.return_value = mock_model

        engine = WhisperEngine()
        engine.load_model()

        min_size = 100 * 1024  # 100 KB
        chunk_size = 40 * 1024  # 40 KB

        # Add first chunk - should buffer
        result1 = engine.transcribe_stream(b"x" * chunk_size, min_chunk_size=min_size)
        assert result1 is None
        assert engine.get_buffer_size() == chunk_size

        # Add second chunk - should buffer
        result2 = engine.transcribe_stream(b"y" * chunk_size, min_chunk_size=min_size)
        assert result2 is None
        assert engine.get_buffer_size() == chunk_size * 2

        # Add third chunk - should trigger transcription (total > 100 KB)
        result3 = engine.transcribe_stream(b"z" * chunk_size, min_chunk_size=min_size)
        assert result3 == "متن تجمعی"
        assert engine.get_buffer_size() == 0

        # Model transcribe should be called once
        mock_model.transcribe.assert_called_once()

    @patch('app.whisper_engine.whisper.load_model')
    def test_transcribe_stream_with_return_partial_false(self, mock_load_model):
        """Test transcribe_stream with return_partial=False only buffers."""
        mock_model = Mock()
        mock_model.device = "cpu"
        mock_load_model.return_value = mock_model

        engine = WhisperEngine()
        engine.load_model()

        # Add a large chunk with return_partial=False
        large_chunk = b"x" * (150 * 1024)  # 150 KB
        result = engine.transcribe_stream(
            large_chunk,
            min_chunk_size=100 * 1024,
            return_partial=False
        )

        # Should return None (buffered, not transcribed)
        assert result is None
        assert engine.get_buffer_size() == len(large_chunk)

        # Model transcribe should not be called
        mock_model.transcribe.assert_not_called()

    @patch('app.whisper_engine.whisper.load_model')
    def test_transcribe_stream_failure_preserves_buffer(self, mock_load_model):
        """Test that transcription failure preserves buffer for retry."""
        mock_model = Mock()
        mock_model.device = "cpu"
        mock_model.transcribe.side_effect = Exception("Transcription error")
        mock_load_model.return_value = mock_model

        engine = WhisperEngine()
        engine.load_model()

        large_chunk = b"x" * (150 * 1024)  # 150 KB

        with pytest.raises(RuntimeError, match="Stream transcription failed"):
            engine.transcribe_stream(large_chunk, min_chunk_size=100 * 1024)

        # Buffer should be preserved on error
        assert engine.get_buffer_size() == len(large_chunk)

    def test_finalize_stream_without_loading_model(self):
        """Test finalize_stream raises error when model is not loaded."""
        engine = WhisperEngine()

        with pytest.raises(ModelNotReadyError, match="Whisper model is not loaded"):
            engine.finalize_stream()

    @patch('app.whisper_engine.whisper.load_model')
    def test_finalize_stream_with_empty_buffer(self, mock_load_model):
        """Test finalize_stream with empty buffer returns empty string."""
        mock_model = Mock()
        mock_model.device = "cpu"
        mock_load_model.return_value = mock_model

        engine = WhisperEngine()
        engine.load_model()

        result = engine.finalize_stream()

        assert result == ""
        mock_model.transcribe.assert_not_called()

    @patch('app.whisper_engine.whisper.load_model')
    def test_finalize_stream_with_buffered_data(self, mock_load_model):
        """Test finalize_stream transcribes remaining buffered data."""
        mock_model = Mock()
        mock_model.device = "cpu"
        mock_model.transcribe.return_value = {
            "text": "متن نهایی",  # "Final text" in Persian
            "segments": []
        }
        mock_load_model.return_value = mock_model

        engine = WhisperEngine()
        engine.load_model()

        # Add some buffered data
        engine.add_audio_chunk(b"x" * 1024)
        assert engine.get_buffer_size() > 0

        result = engine.finalize_stream()

        assert result == "متن نهایی"
        assert engine.get_buffer_size() == 0
        mock_model.transcribe.assert_called_once()

    @patch('app.whisper_engine.whisper.load_model')
    def test_finalize_stream_clears_buffer_on_error(self, mock_load_model):
        """Test finalize_stream clears buffer even on error."""
        mock_model = Mock()
        mock_model.device = "cpu"
        mock_model.transcribe.side_effect = Exception("Finalization error")
        mock_load_model.return_value = mock_model

        engine = WhisperEngine()
        engine.load_model()

        # Add some buffered data
        engine.add_audio_chunk(b"x" * 1024)
        assert engine.get_buffer_size() > 0

        with pytest.raises(RuntimeError, match="Stream finalization failed"):
            engine.finalize_stream()

        # Buffer should be cleared even on error to prevent memory leaks
        assert engine.get_buffer_size() == 0

    @patch('app.whisper_engine.whisper.load_model')
    def test_streaming_workflow(self, mock_load_model):
        """Test complete streaming workflow with multiple chunks and finalization."""
        mock_model = Mock()
        mock_model.device = "cpu"

        # Mock different responses for partial and final transcriptions
        transcription_count = [0]

        def mock_transcribe(*args, **kwargs):
            transcription_count[0] += 1
            if transcription_count[0] == 1:
                return {"text": "بخش اول", "segments": []}  # "Part one"
            else:
                return {"text": "بخش دوم", "segments": []}  # "Part two"

        mock_model.transcribe = mock_transcribe
        mock_load_model.return_value = mock_model

        engine = WhisperEngine()
        engine.load_model()

        min_size = 100 * 1024

        # Add chunks that trigger partial transcription
        result1 = engine.transcribe_stream(b"x" * (150 * 1024), min_chunk_size=min_size)
        assert result1 == "بخش اول"
        assert engine.get_buffer_size() == 0

        # Add smaller chunks that don't trigger transcription
        engine.transcribe_stream(b"y" * (50 * 1024), min_chunk_size=min_size)
        assert engine.get_buffer_size() == 50 * 1024

        # Finalize to get remaining content
        result2 = engine.finalize_stream()
        assert result2 == "بخش دوم"
        assert engine.get_buffer_size() == 0

