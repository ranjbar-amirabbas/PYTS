"""
Audio processing module for the Persian Transcription API.

This module handles audio format validation, detection, and conversion
for the transcription service.
"""

import os
import mimetypes
import tempfile
import logging
from enum import Enum
from pathlib import Path
from typing import Optional, Union
import ffmpeg


class AudioFormat(Enum):
    """Supported audio formats."""
    WAV = "audio/wav"
    MP3 = "audio/mpeg"
    OGG = "audio/ogg"
    M4A = "audio/mp4"


# Mapping of file extensions to AudioFormat
EXTENSION_TO_FORMAT = {
    ".wav": AudioFormat.WAV,
    ".mp3": AudioFormat.MP3,
    ".ogg": AudioFormat.OGG,
    ".m4a": AudioFormat.M4A,
}

# Magic bytes (file signatures) for format detection
MAGIC_BYTES = {
    AudioFormat.WAV: [b"RIFF"],
    AudioFormat.MP3: [b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"ID3"],
    AudioFormat.OGG: [b"OggS"],
    AudioFormat.M4A: [b"ftyp"],  # M4A files have 'ftyp' at offset 4
}


class UnsupportedFormatError(Exception):
    """Exception raised when an unsupported audio format is encountered."""
    pass


class AudioConversionError(Exception):
    """Exception raised when audio conversion fails."""
    pass


class AudioProcessor:
    """
    Handles audio file validation, format detection, and conversion.
    
    This class provides methods to validate audio formats and prepare
    audio files for transcription processing.
    """
    
    SUPPORTED_FORMATS = [AudioFormat.WAV, AudioFormat.MP3, AudioFormat.OGG, AudioFormat.M4A]
    
    # Whisper model requirements
    WHISPER_SAMPLE_RATE = 16000  # 16kHz
    WHISPER_CHANNELS = 1  # Mono
    
    def __init__(self):
        """Initialize the AudioProcessor."""
        # Initialize mimetypes for better format detection
        mimetypes.init()
        self.logger = logging.getLogger(__name__)
    
    def validate_format(self, file_path: Union[str, Path]) -> bool:
        """
        Validate if the audio file is in a supported format.
        
        Args:
            file_path: Path to the audio file
            
        Returns:
            True if the format is supported
            
        Raises:
            UnsupportedFormatError: If the format is not supported
            FileNotFoundError: If the file does not exist
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")
        
        # Detect the format
        detected_format = self.detect_format(file_path)
        
        if detected_format is None:
            raise UnsupportedFormatError(
                f"Audio format not supported. Supported formats: WAV, MP3, OGG, M4A"
            )
        
        return True
    
    def detect_format(self, file_path: Union[str, Path]) -> Optional[AudioFormat]:
        """
        Detect the audio format using file headers and extensions.
        
        This method uses a two-step approach:
        1. Check file extension
        2. Verify with magic bytes (file signature)
        
        Args:
            file_path: Path to the audio file
            
        Returns:
            AudioFormat if detected and supported, None otherwise
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            return None
        
        # Step 1: Check file extension
        extension = file_path.suffix.lower()
        format_from_extension = EXTENSION_TO_FORMAT.get(extension)
        
        # Step 2: Verify with magic bytes
        format_from_magic = self._detect_format_from_magic_bytes(file_path)
        
        # If both methods agree, return the format
        if format_from_extension and format_from_magic:
            if format_from_extension == format_from_magic:
                return format_from_extension
        
        # If extension detection worked but magic bytes didn't, trust extension
        # (some files might have unusual headers but valid extensions)
        if format_from_extension and format_from_extension in self.SUPPORTED_FORMATS:
            return format_from_extension
        
        # If magic bytes detection worked, use that
        if format_from_magic and format_from_magic in self.SUPPORTED_FORMATS:
            return format_from_magic
        
        return None
    
    def _detect_format_from_magic_bytes(self, file_path: Path) -> Optional[AudioFormat]:
        """
        Detect audio format by reading file signature (magic bytes).
        
        Args:
            file_path: Path to the audio file
            
        Returns:
            AudioFormat if detected, None otherwise
        """
        try:
            with open(file_path, "rb") as f:
                # Read first 12 bytes (enough for most signatures)
                header = f.read(12)
                
                if not header:
                    return None
                
                # Check WAV format (RIFF header)
                if header.startswith(b"RIFF") and b"WAVE" in header:
                    return AudioFormat.WAV
                
                # Check MP3 format (ID3 tag or MPEG frame sync)
                if header.startswith(b"ID3"):
                    return AudioFormat.MP3
                if header[0:2] in [b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"]:
                    return AudioFormat.MP3
                
                # Check OGG format
                if header.startswith(b"OggS"):
                    return AudioFormat.OGG
                
                # Check M4A format (ftyp box at offset 4)
                if len(header) >= 8 and header[4:8] == b"ftyp":
                    return AudioFormat.M4A
                
        except (IOError, OSError):
            return None
        
        return None
    
    def get_format_info(self, file_path: Union[str, Path]) -> dict:
        """
        Get information about the audio file format.
        
        Args:
            file_path: Path to the audio file
            
        Returns:
            Dictionary with format information
        """
        file_path = Path(file_path)
        
        detected_format = self.detect_format(file_path)
        
        return {
            "file_path": str(file_path),
            "file_size": file_path.stat().st_size if file_path.exists() else 0,
            "extension": file_path.suffix.lower(),
            "detected_format": detected_format.value if detected_format else None,
            "is_supported": detected_format in self.SUPPORTED_FORMATS if detected_format else False,
        }
    
    def convert_to_whisper_format(
        self,
        input_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        normalize: bool = True
    ) -> Path:
        """
        Convert audio file to Whisper-compatible format (16kHz mono WAV).
        
        This method converts any supported audio format to the format required
        by the Whisper model: 16kHz sample rate, mono channel, WAV format.
        
        Args:
            input_path: Path to the input audio file
            output_path: Path for the output file (optional, creates temp file if not provided)
            normalize: Whether to apply audio normalization (default: True)
            
        Returns:
            Path to the converted audio file
            
        Raises:
            FileNotFoundError: If the input file doesn't exist
            UnsupportedFormatError: If the input format is not supported
            AudioConversionError: If the conversion fails
        """
        input_path = Path(input_path)
        
        # Validate input file exists
        if not input_path.exists():
            raise FileNotFoundError(f"Input audio file not found: {input_path}")
        
        # Validate format is supported
        self.validate_format(input_path)
        
        # Create output path if not provided
        if output_path is None:
            # Create a temporary file with .wav extension
            temp_fd, temp_path = tempfile.mkstemp(suffix=".wav", prefix="whisper_")
            os.close(temp_fd)  # Close the file descriptor
            output_path = Path(temp_path)
        else:
            output_path = Path(output_path)
        
        try:
            self.logger.info(f"Converting audio file: {input_path} -> {output_path}")
            
            # Build FFmpeg pipeline
            stream = ffmpeg.input(str(input_path))
            
            # Apply audio normalization if requested
            if normalize:
                # Use loudnorm filter for audio normalization
                # This normalizes the audio to a target loudness level
                stream = stream.filter("loudnorm", I=-16, TP=-1.5, LRA=11)
            
            # Configure output: 16kHz, mono, WAV format
            stream = ffmpeg.output(
                stream,
                str(output_path),
                acodec="pcm_s16le",  # PCM 16-bit little-endian
                ac=self.WHISPER_CHANNELS,  # Mono
                ar=self.WHISPER_SAMPLE_RATE,  # 16kHz
                format="wav"
            )
            
            # Run the conversion
            # overwrite_output=True allows overwriting existing files
            # capture_stderr=True captures error messages
            ffmpeg.run(stream, overwrite_output=True, capture_stderr=True)
            
            self.logger.info(f"Audio conversion successful: {output_path}")
            
            # Verify the output file was created
            if not output_path.exists() or output_path.stat().st_size == 0:
                raise AudioConversionError("Conversion produced empty or missing output file")
            
            return output_path
            
        except ffmpeg.Error as e:
            # FFmpeg error occurred
            error_message = e.stderr.decode() if e.stderr else str(e)
            self.logger.error(f"FFmpeg conversion error: {error_message}")
            
            # Clean up output file if it was created
            if output_path.exists():
                try:
                    output_path.unlink()
                except Exception:
                    pass
            
            raise AudioConversionError(
                f"Failed to convert audio file: {error_message}"
            ) from e
            
        except Exception as e:
            # Other unexpected errors
            self.logger.error(f"Unexpected error during audio conversion: {str(e)}")
            
            # Clean up output file if it was created
            if output_path.exists():
                try:
                    output_path.unlink()
                except Exception:
                    pass
            
            raise AudioConversionError(
                f"Unexpected error during audio conversion: {str(e)}"
            ) from e
    
    def normalize_audio(self, audio_data: bytes) -> bytes:
        """
        Normalize audio data.
        
        This method normalizes audio data by writing it to a temporary file,
        converting it with normalization, and reading it back.
        
        Args:
            audio_data: Raw audio data bytes
            
        Returns:
            Normalized audio data bytes
            
        Raises:
            AudioConversionError: If normalization fails
        """
        # Create temporary input file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_input:
            temp_input.write(audio_data)
            temp_input_path = Path(temp_input.name)
        
        try:
            # Convert with normalization
            output_path = self.convert_to_whisper_format(
                temp_input_path,
                normalize=True
            )
            
            # Read normalized data
            with open(output_path, "rb") as f:
                normalized_data = f.read()
            
            # Clean up output file
            output_path.unlink()
            
            return normalized_data
            
        finally:
            # Clean up input file
            if temp_input_path.exists():
                temp_input_path.unlink()
