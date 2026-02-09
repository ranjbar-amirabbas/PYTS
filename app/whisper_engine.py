"""
Whisper model engine for Persian speech transcription.

This module handles loading and managing the Whisper model for
Persian language transcription.
"""

import logging
import tempfile
from pathlib import Path
from typing import Optional, Literal
import whisper
from whisper import Whisper


# Type alias for model sizes
ModelSize = Literal["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]


class ModelNotReadyError(Exception):
    """Exception raised when attempting to use a model that isn't loaded."""
    pass


class WhisperEngine:
    """
    Manages the Whisper model for Persian speech transcription.
    
    This class handles model initialization, loading, and provides
    a readiness check to ensure the model is available before use.
    """
    
    def __init__(
        self,
        model_size: ModelSize = "medium",
        language: str = "fa",
        device: Optional[str] = None
    ):
        """
        Initialize the WhisperEngine.

        Args:
            model_size: Size of the Whisper model to load.
                       Options: tiny, base, small, medium, large, large-v2, large-v3
                       Default: medium (good balance of speed and accuracy for Persian)
            language: Language code for transcription. Default: "fa" (Persian/Farsi)
            device: Device to run the model on ("cuda" or "cpu").
                   If None, automatically selects CUDA if available, otherwise CPU.
        """
        self.model_size = model_size
        self.language = language
        self.device = device
        self._model: Optional[Whisper] = None
        self._is_ready = False
        self.logger = logging.getLogger(__name__)

        # Streaming state management
        self._stream_buffer: list[bytes] = []
        self._stream_buffer_size = 0
        self._max_buffer_size = 5 * 1024 * 1024  # 5 MB buffer limit

        self.logger.info(
            f"Initializing WhisperEngine with model_size={model_size}, "
            f"language={language}, device={device or 'auto'}"
        )

    
    def load_model(self) -> None:
        """
        Load the Whisper model into memory.
        
        This method downloads the model if not already cached and loads it
        into memory. The model is configured for the specified language.
        
        Raises:
            RuntimeError: If model loading fails
        """
        try:
            self.logger.info(f"Loading Whisper model: {self.model_size}")
            
            # Load the model
            # Whisper will automatically download the model if not cached
            # Models are cached in ~/.cache/whisper by default
            self._model = whisper.load_model(
                name=self.model_size,
                device=self.device
            )
            
            self._is_ready = True
            
            self.logger.info(
                f"Whisper model loaded successfully: {self.model_size} "
                f"(device: {self._model.device})"
            )
            
        except Exception as e:
            self._is_ready = False
            self.logger.error(f"Failed to load Whisper model: {str(e)}")
            raise RuntimeError(f"Failed to load Whisper model: {str(e)}") from e
    
    def is_ready(self) -> bool:
        """
        Check if the model is loaded and ready for transcription.
        
        Returns:
            True if the model is loaded and ready, False otherwise
        """
        return self._is_ready and self._model is not None
    
    def get_model_info(self) -> dict:
        """
        Get information about the loaded model.
        
        Returns:
            Dictionary containing model information
        """
        return {
            "model_size": self.model_size,
            "language": self.language,
            "device": str(self._model.device) if self._model else None,
            "is_ready": self.is_ready(),
        }
    
    def transcribe(
        self,
        audio_path: str,
        task: str = "transcribe",
        **kwargs
    ) -> str:
        """
        Transcribe an audio file to text.
        
        Args:
            audio_path: Path to the audio file (should be in Whisper-compatible format)
            task: Task type - "transcribe" or "translate". Default: "transcribe"
            **kwargs: Additional arguments to pass to whisper.transcribe()
            
        Returns:
            Transcribed text as a plain string
            
        Raises:
            ModelNotReadyError: If the model is not loaded
            FileNotFoundError: If the audio file doesn't exist
            RuntimeError: If transcription fails
        """
        if not self.is_ready():
            raise ModelNotReadyError(
                "Whisper model is not loaded. Call load_model() first."
            )
        
        audio_path_obj = Path(audio_path)
        if not audio_path_obj.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        try:
            self.logger.info(f"Transcribing audio file: {audio_path}")
            
            # Transcribe the audio
            # Set language to Persian and disable timestamps for plain text output
            result = self._model.transcribe(
                audio=str(audio_path),
                language=self.language,
                task=task,
                verbose=False,  # Disable verbose output
                **kwargs
            )
            
            # Extract the text from the result
            # The result is a dictionary with 'text', 'segments', and other metadata
            # We only return the plain text as per requirements
            transcription_text = result.get("text", "").strip()
            
            self.logger.info(
                f"Transcription completed successfully. "
                f"Text length: {len(transcription_text)} characters"
            )
            
            return transcription_text
            
        except Exception as e:
            self.logger.error(f"Transcription failed: {str(e)}")
            raise RuntimeError(f"Transcription failed: {str(e)}") from e
    
    def transcribe_chunk(
        self,
        audio_path: str,
        **kwargs
    ) -> str:
        """
        Transcribe an audio chunk for streaming transcription.
        
        This is a wrapper around transcribe() for streaming use cases.
        For better streaming accuracy, consider using overlapping chunks.
        
        Args:
            audio_path: Path to the audio chunk file
            **kwargs: Additional arguments to pass to whisper.transcribe()
            
        Returns:
            Transcribed text as a plain string
            
        Raises:
            ModelNotReadyError: If the model is not loaded
            FileNotFoundError: If the audio file doesn't exist
            RuntimeError: If transcription fails
        """
        # For now, this is the same as transcribe()
        # In the future, we could add chunk-specific optimizations
        return self.transcribe(audio_path, **kwargs)
    def add_audio_chunk(self, audio_chunk: bytes) -> None:
        """
        Add an audio chunk to the streaming buffer.

        This method buffers audio chunks for streaming transcription.
        Chunks are accumulated until they reach a sufficient size for
        accurate transcription.

        Args:
            audio_chunk: Raw audio data bytes

        Raises:
            ValueError: If buffer size exceeds maximum limit
        """
        if not audio_chunk:
            return

        chunk_size = len(audio_chunk)

        # Check if adding this chunk would exceed buffer limit
        if self._stream_buffer_size + chunk_size > self._max_buffer_size:
            raise ValueError(
                f"Stream buffer size would exceed maximum limit of "
                f"{self._max_buffer_size} bytes"
            )

        self._stream_buffer.append(audio_chunk)
        self._stream_buffer_size += chunk_size

        self.logger.debug(
            f"Added audio chunk: {chunk_size} bytes. "
            f"Total buffer size: {self._stream_buffer_size} bytes"
        )

    def get_buffer_size(self) -> int:
        """
        Get the current size of the streaming buffer.

        Returns:
            Size of buffered audio data in bytes
        """
        return self._stream_buffer_size

    def clear_buffer(self) -> None:
        """
        Clear the streaming buffer.

        This should be called after processing buffered chunks or
        when starting a new streaming session.
        """
        self._stream_buffer.clear()
        self._stream_buffer_size = 0
        self.logger.debug("Streaming buffer cleared")

    def transcribe_stream(
        self,
        audio_chunk: bytes,
        min_chunk_size: int = 100 * 1024,  # 100 KB minimum
        return_partial: bool = True,
        **kwargs
    ) -> Optional[str]:
        """
        Transcribe audio chunks for streaming transcription.

        This method implements streaming transcription with chunk buffering
        for better accuracy. Audio chunks are buffered until they reach a
        minimum size, then transcribed and the buffer is cleared.

        The buffering strategy improves accuracy by:
        1. Ensuring sufficient audio context for the model
        2. Reducing the number of transcription calls
        3. Allowing the model to process complete phrases/sentences

        Args:
            audio_chunk: Raw audio data bytes (should be in Whisper-compatible format)
            min_chunk_size: Minimum buffer size before transcription (default: 100 KB)
            return_partial: If True, return partial results when buffer reaches threshold.
                          If False, only buffer the chunk without transcribing.
            **kwargs: Additional arguments to pass to whisper.transcribe()

        Returns:
            Transcribed text if buffer threshold is reached and return_partial is True,
            None otherwise

        Raises:
            ModelNotReadyError: If the model is not loaded
            RuntimeError: If transcription fails
            ValueError: If buffer size exceeds maximum limit
        """
        if not self.is_ready():
            raise ModelNotReadyError(
                "Whisper model is not loaded. Call load_model() first."
            )

        # Add chunk to buffer
        self.add_audio_chunk(audio_chunk)

        # Check if we should transcribe the buffered audio
        if not return_partial or self._stream_buffer_size < min_chunk_size:
            self.logger.debug(
                f"Buffering audio chunk. Current size: {self._stream_buffer_size} bytes, "
                f"threshold: {min_chunk_size} bytes"
            )
            return None

        # Buffer has reached threshold, transcribe it
        try:
            self.logger.info(
                f"Transcribing buffered audio: {self._stream_buffer_size} bytes"
            )

            # Combine all buffered chunks
            combined_audio = b"".join(self._stream_buffer)

            # Write to temporary file for Whisper processing
            with tempfile.NamedTemporaryFile(
                suffix=".wav",
                delete=False,
                mode="wb"
            ) as temp_file:
                temp_file.write(combined_audio)
                temp_path = temp_file.name

            try:
                # Transcribe the buffered audio
                result = self._model.transcribe(
                    audio=temp_path,
                    language=self.language,
                    task="transcribe",
                    verbose=False,
                    **kwargs
                )

                # Extract text
                transcription_text = result.get("text", "").strip()

                self.logger.info(
                    f"Stream transcription completed. "
                    f"Text length: {len(transcription_text)} characters"
                )

                # Clear buffer after successful transcription
                self.clear_buffer()

                return transcription_text

            finally:
                # Clean up temporary file
                try:
                    Path(temp_path).unlink()
                except Exception as e:
                    self.logger.warning(f"Failed to delete temp file {temp_path}: {e}")

        except Exception as e:
            self.logger.error(f"Stream transcription failed: {str(e)}")
            # Don't clear buffer on error - allow retry
            raise RuntimeError(f"Stream transcription failed: {str(e)}") from e

    def finalize_stream(self, **kwargs) -> str:
        """
        Finalize streaming transcription and return any remaining buffered content.

        This method should be called when a streaming session ends to ensure
        all buffered audio is transcribed, even if it hasn't reached the
        minimum chunk size threshold.

        Args:
            **kwargs: Additional arguments to pass to whisper.transcribe()

        Returns:
            Transcribed text from remaining buffer, or empty string if buffer is empty

        Raises:
            ModelNotReadyError: If the model is not loaded
            RuntimeError: If transcription fails
        """
        if not self.is_ready():
            raise ModelNotReadyError(
                "Whisper model is not loaded. Call load_model() first."
            )

        # If buffer is empty, return empty string
        if self._stream_buffer_size == 0:
            self.logger.debug("No buffered audio to finalize")
            return ""

        try:
            self.logger.info(
                f"Finalizing stream transcription: {self._stream_buffer_size} bytes"
            )

            # Combine all buffered chunks
            combined_audio = b"".join(self._stream_buffer)

            # Write to temporary file for Whisper processing
            with tempfile.NamedTemporaryFile(
                suffix=".wav",
                delete=False,
                mode="wb"
            ) as temp_file:
                temp_file.write(combined_audio)
                temp_path = temp_file.name

            try:
                # Transcribe the remaining buffered audio
                result = self._model.transcribe(
                    audio=temp_path,
                    language=self.language,
                    task="transcribe",
                    verbose=False,
                    **kwargs
                )

                # Extract text
                transcription_text = result.get("text", "").strip()

                self.logger.info(
                    f"Stream finalization completed. "
                    f"Text length: {len(transcription_text)} characters"
                )

                # Clear buffer after successful transcription
                self.clear_buffer()

                return transcription_text

            finally:
                # Clean up temporary file
                try:
                    Path(temp_path).unlink()
                except Exception as e:
                    self.logger.warning(f"Failed to delete temp file {temp_path}: {e}")

        except Exception as e:
            self.logger.error(f"Stream finalization failed: {str(e)}")
            # Clear buffer even on error to prevent memory leaks
            self.clear_buffer()
            raise RuntimeError(f"Stream finalization failed: {str(e)}") from e

    
    def unload_model(self) -> None:
        """
        Unload the model from memory.
        
        This can be useful for freeing up resources when the model
        is no longer needed.
        """
        if self._model is not None:
            self.logger.info("Unloading Whisper model")
            self._model = None
            self._is_ready = False
            self.logger.info("Whisper model unloaded")
