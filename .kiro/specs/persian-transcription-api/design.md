# Design Document: Persian Transcription API

## Overview

The Persian Transcription API is a Dockerized REST service that provides speech-to-text transcription for Persian (Farsi) audio. The system uses Whisper, OpenAI's multilingual speech recognition model, which has excellent Persian language support. The service offers both batch processing (upload complete files) and streaming transcription capabilities, running entirely offline once deployed.

### Key Design Decisions

1. **Whisper Model Selection**: We'll use OpenAI's Whisper model (specifically the "medium" or "small" variant) as it provides excellent Persian transcription quality with reasonable performance. Whisper supports 99 languages including Persian and can run locally without internet connectivity.

2. **Framework Choice**: FastAPI for the REST API layer due to its high performance, automatic OpenAPI documentation, and native async support for handling concurrent requests and streaming.

3. **Audio Processing**: FFmpeg for audio format conversion and preprocessing, ensuring all supported formats (WAV, MP3, OGG, M4A) can be normalized before transcription.

4. **Containerization**: Multi-stage Docker build to minimize image size while including all dependencies and the Whisper model weights.

5. **Streaming Architecture**: WebSocket-based streaming for real-time transcription, allowing bidirectional communication with chunked audio processing.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Container                      │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │           FastAPI Application                   │    │
│  │                                                 │    │
│  │  ┌──────────────┐      ┌──────────────────┐   │    │
│  │  │   REST API   │      │  WebSocket API   │   │    │
│  │  │   Endpoints  │      │   (Streaming)    │   │    │
│  │  └──────┬───────┘      └────────┬─────────┘   │    │
│  │         │                       │             │    │
│  │         └───────────┬───────────┘             │    │
│  │                     │                         │    │
│  │         ┌───────────▼──────────────┐          │    │
│  │         │  Transcription Service   │          │    │
│  │         │  (Business Logic)        │          │    │
│  │         └───────────┬──────────────┘          │    │
│  │                     │                         │    │
│  │         ┌───────────▼──────────────┐          │    │
│  │         │   Audio Processor        │          │    │
│  │         │   (FFmpeg wrapper)       │          │    │
│  │         └───────────┬──────────────┘          │    │
│  │                     │                         │    │
│  │         ┌───────────▼──────────────┐          │    │
│  │         │   Whisper Model Engine   │          │    │
│  │         │   (Persian optimized)    │          │    │
│  │         └──────────────────────────┘          │    │
│  └─────────────────────────────────────────────────┘    │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │         File System / Volume Mounts             │    │
│  │  - Model weights cache                          │    │
│  │  - Temporary audio processing                   │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

### Component Interaction Flow

**Batch Processing Flow:**
```
Client → REST API → Transcription Service → Audio Processor → Whisper Engine → Response
```

**Streaming Flow:**
```
Client ←→ WebSocket API ←→ Transcription Service → Audio Processor → Whisper Engine
         (bidirectional)
```

## Components and Interfaces

### 1. REST API Layer (FastAPI)

**Responsibilities:**
- HTTP request handling and routing
- Request validation and error responses
- File upload management
- Response formatting

**Endpoints:**

```python
POST /api/v1/transcribe/batch
  - Accept: multipart/form-data (audio file)
  - Returns: { "job_id": str, "status": str }

GET /api/v1/transcribe/batch/{job_id}
  - Returns: { "job_id": str, "status": str, "transcription": str | null, "error": str | null }

GET /api/v1/health
  - Returns: { "status": str, "model_loaded": bool }

WebSocket /api/v1/transcribe/stream
  - Bidirectional streaming for real-time transcription
  - Client sends: audio chunks (binary)
  - Server sends: { "type": "partial" | "final", "text": str }
```

### 2. Transcription Service

**Responsibilities:**
- Orchestrate transcription workflow
- Manage job state for batch processing
- Coordinate audio processing and model inference
- Handle concurrent requests

**Interface:**

```python
class TranscriptionService:
    async def transcribe_batch(audio_file: UploadFile) -> JobResult
    async def get_batch_status(job_id: str) -> JobStatus
    async def transcribe_stream(audio_chunk: bytes) -> TranscriptionChunk
    def initialize_model() -> None
```

### 3. Audio Processor

**Responsibilities:**
- Validate audio format
- Convert audio to Whisper-compatible format (16kHz, mono, WAV)
- Handle audio chunking for streaming
- Normalize audio levels

**Interface:**

```python
class AudioProcessor:
    def validate_format(file_path: str) -> bool
    def convert_to_wav(input_path: str, output_path: str) -> str
    def normalize_audio(audio_data: bytes) -> bytes
    def chunk_audio_for_streaming(audio_data: bytes, chunk_size: int) -> Iterator[bytes]
```

### 4. Whisper Model Engine

**Responsibilities:**
- Load and initialize Whisper model
- Perform speech-to-text inference
- Optimize for Persian language
- Manage GPU/CPU resources

**Interface:**

```python
class WhisperEngine:
    def __init__(model_size: str = "medium", language: str = "fa")
    def transcribe(audio_path: str) -> str
    def transcribe_chunk(audio_chunk: bytes) -> str
    def is_ready() -> bool
```

### 5. Job Manager (for Batch Processing)

**Responsibilities:**
- Track batch job states
- Store job results temporarily
- Clean up completed jobs
- Handle job timeouts

**Interface:**

```python
class JobManager:
    def create_job(audio_file: str) -> str  # Returns job_id
    def update_job_status(job_id: str, status: JobStatus) -> None
    def get_job(job_id: str) -> Job | None
    def cleanup_old_jobs() -> None
```

## Data Models

### Job Status Model

```python
class JobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Job:
    job_id: str
    status: JobStatus
    audio_file_path: str
    transcription: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
```

### API Request/Response Models

```python
class BatchTranscribeRequest:
    audio_file: UploadFile

class BatchTranscribeResponse:
    job_id: str
    status: str

class BatchStatusResponse:
    job_id: str
    status: str
    transcription: str | None
    error: str | None

class StreamTranscriptionMessage:
    type: Literal["partial", "final", "error"]
    text: str
    timestamp: float | None

class HealthResponse:
    status: str
    model_loaded: bool
    model_size: str
```

### Audio Format Specifications

```python
class AudioFormat(Enum):
    WAV = "audio/wav"
    MP3 = "audio/mpeg"
    OGG = "audio/ogg"
    M4A = "audio/mp4"

SUPPORTED_FORMATS = [AudioFormat.WAV, AudioFormat.MP3, AudioFormat.OGG, AudioFormat.M4A]
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB
WHISPER_SAMPLE_RATE = 16000  # 16kHz
WHISPER_CHANNELS = 1  # Mono
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property 1: Supported Format Acceptance
*For any* audio file in a supported format (WAV, MP3, OGG, M4A), the Transcription_Service should accept and process it without format-related errors.
**Validates: Requirements 1.1, 1.2, 1.3, 1.4**

### Property 2: Unsupported Format Rejection
*For any* audio file in an unsupported format, the Transcription_Service should return an error indicating the format is not supported.
**Validates: Requirements 1.5**

### Property 3: Variable Duration Handling
*For any* audio file duration from short clips to long recordings, the Transcription_Service should process it without arbitrary size limitations.
**Validates: Requirements 1.6**

### Property 4: Batch Upload Returns Job ID
*For any* valid audio file uploaded to the batch endpoint, the Transcription_Service should return a unique processing identifier.
**Validates: Requirements 2.1**

### Property 5: Persian Text Output
*For any* Persian audio input, the transcription output should be in Persian script (not Latin transliteration or other scripts).
**Validates: Requirements 2.2, 4.2**

### Property 6: Plain Text Output Format
*For any* completed transcription, the result should be plain text without timestamps, metadata, or additional formatting.
**Validates: Requirements 2.3, 8.1, 8.2, 8.3**

### Property 7: Job Status Retrieval
*For any* job ID created by the system, querying the status endpoint should return a valid processing state (pending, processing, completed, or failed).
**Validates: Requirements 2.4**

### Property 8: Descriptive Error Messages
*For any* processing failure (corrupted files, invalid input, processing errors), the Transcription_Service should return a descriptive error message without crashing.
**Validates: Requirements 2.5, 9.1, 9.2**

### Property 9: Streaming Connection Establishment
*For any* streaming connection request, the Transcription_Service should establish a bidirectional communication channel.
**Validates: Requirements 3.1**

### Property 10: Incremental Stream Processing
*For any* audio chunks streamed to the service, the Transcription_Service should process them incrementally and return partial results as they become available.
**Validates: Requirements 3.2, 3.3**

### Property 11: Stream Finalization
*For any* streaming connection that is closed, the Transcription_Service should finalize and return any remaining transcription content.
**Validates: Requirements 3.4**

### Property 12: Streaming Error Handling
*For any* error encountered during streaming, the Transcription_Service should notify the client and maintain connection stability where possible.
**Validates: Requirements 3.5**

### Property 13: JSON Response Format
*For any* valid API request, the REST_API should return responses in valid JSON format.
**Validates: Requirements 5.5**

### Property 14: HTTP Error Codes
*For any* invalid API request, the REST_API should return appropriate HTTP status codes (4xx for client errors, 5xx for server errors) with error messages.
**Validates: Requirements 5.6**

### Property 15: Concurrent Request Handling
*For any* set of concurrent requests, the Transcription_Service should handle them all without failures or data corruption.
**Validates: Requirements 9.4, 10.4**

### Property 16: Error Logging
*For any* error condition, the Transcription_Service should create log entries for debugging and monitoring.
**Validates: Requirements 9.5**

### Property 17: Short Clip Performance
*For any* short audio clip (under 30 seconds), the Transcription_Service should return results within a reasonable time (under 10 seconds for batch processing).
**Validates: Requirements 10.2**

### Property 18: Linear Performance Scaling
*For any* two audio files where one is twice the duration of the other, the processing time should scale approximately linearly (within 2x factor).
**Validates: Requirements 10.5**

## Error Handling

### Error Categories

1. **Client Errors (4xx)**
   - 400 Bad Request: Invalid audio format, corrupted file, missing required fields
   - 404 Not Found: Job ID not found
   - 413 Payload Too Large: File exceeds maximum size
   - 415 Unsupported Media Type: Audio format not supported

2. **Server Errors (5xx)**
   - 500 Internal Server Error: Unexpected processing failure
   - 503 Service Unavailable: Model not loaded or system resources exhausted

### Error Response Format

All errors return JSON with consistent structure:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error description",
    "details": "Additional context (optional)"
  }
}
```

### Error Handling Strategy

1. **Input Validation**: Validate audio format and file integrity before processing
2. **Graceful Degradation**: Return partial results when possible (e.g., in streaming mode)
3. **Resource Management**: Monitor memory/CPU usage and reject requests if resources are insufficient
4. **Timeout Handling**: Set reasonable timeouts for long-running transcriptions
5. **Logging**: Log all errors with context (job ID, file info, stack traces) for debugging
6. **Retry Logic**: For transient failures, clients can retry with exponential backoff

### Specific Error Scenarios

- **Corrupted Audio File**: Return 400 with message "Audio file is corrupted or unreadable"
- **Unsupported Format**: Return 415 with message "Audio format not supported. Supported formats: WAV, MP3, OGG, M4A"
- **Model Not Loaded**: Return 503 with message "Transcription service is initializing. Please retry in a few moments"
- **Processing Timeout**: Return 500 with message "Transcription processing exceeded timeout limit"
- **Concurrent Limit Exceeded**: Return 503 with message "Server is at capacity. Please retry later"

## Testing Strategy

### Dual Testing Approach

The testing strategy employs both unit tests and property-based tests to ensure comprehensive coverage:

- **Unit Tests**: Verify specific examples, edge cases, error conditions, and integration points
- **Property-Based Tests**: Verify universal properties across randomized inputs

Together, these approaches provide comprehensive coverage where unit tests catch concrete bugs and property-based tests verify general correctness across a wide input space.

### Property-Based Testing Configuration

**Framework**: We'll use `hypothesis` (Python) for property-based testing, which provides:
- Automatic test case generation
- Shrinking of failing examples
- Stateful testing for complex scenarios

**Configuration**:
- Minimum 100 iterations per property test (due to randomization)
- Each property test must reference its design document property
- Tag format: `# Feature: persian-transcription-api, Property {number}: {property_text}`

**Example Property Test Structure**:

```python
from hypothesis import given, strategies as st
import pytest

# Feature: persian-transcription-api, Property 1: Supported Format Acceptance
@given(audio_format=st.sampled_from(['wav', 'mp3', 'ogg', 'm4a']))
@pytest.mark.property_test
def test_supported_format_acceptance(audio_format):
    """For any audio file in a supported format, the service accepts it."""
    audio_file = generate_audio_file(format=audio_format)
    response = client.post("/api/v1/transcribe/batch", files={"audio_file": audio_file})
    assert response.status_code == 200
    assert "job_id" in response.json()
```

### Unit Testing Strategy

**Focus Areas**:
1. **API Endpoint Tests**: Verify each endpoint's basic functionality
2. **Audio Format Conversion**: Test FFmpeg wrapper with known audio files
3. **Job Management**: Test job creation, status updates, and cleanup
4. **Error Conditions**: Test specific error scenarios (corrupted files, invalid formats)
5. **Integration Tests**: Test full workflow from upload to transcription result

**Example Unit Test**:

```python
def test_batch_upload_returns_job_id():
    """Test that uploading a valid audio file returns a job ID."""
    with open("test_audio.wav", "rb") as f:
        response = client.post("/api/v1/transcribe/batch", files={"audio_file": f})
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert isinstance(data["job_id"], str)
    assert len(data["job_id"]) > 0
```

### Testing Layers

1. **Unit Tests** (Fast, Isolated)
   - Audio processor functions
   - Job manager operations
   - API request/response validation
   - Error handling logic

2. **Property-Based Tests** (Comprehensive, Randomized)
   - Format acceptance across all supported types
   - Concurrent request handling
   - Output format validation
   - Error message consistency

3. **Integration Tests** (End-to-End)
   - Full batch transcription workflow
   - Streaming transcription workflow
   - Docker container startup and health checks
   - Offline operation verification

4. **Performance Tests** (Benchmarking)
   - Processing time for various audio durations
   - Concurrent request throughput
   - Memory usage under load
   - Linear scaling verification

### Test Data Strategy

- **Synthetic Audio**: Generate test audio files with known content for validation
- **Real Persian Audio**: Include sample Persian speech recordings for accuracy testing
- **Edge Cases**: Empty files, very short clips, very long recordings, corrupted data
- **Format Variations**: Test files in all supported formats with various encodings

### Continuous Testing

- Run unit tests on every code change
- Run property-based tests in CI/CD pipeline
- Run integration tests before deployment
- Run performance tests periodically to detect regressions

## Implementation Notes

### Whisper Model Selection

For optimal balance between speed and accuracy for Persian:
- **Development/Testing**: Use `whisper-small` (244M parameters) for faster iteration
- **Production**: Use `whisper-medium` (769M parameters) for better accuracy
- **High-Accuracy**: Use `whisper-large` (1550M parameters) if accuracy is critical and resources allow

### Performance Optimization

1. **Model Loading**: Load model once at startup, keep in memory
2. **Audio Preprocessing**: Use FFmpeg for efficient format conversion
3. **Batch Processing**: Process multiple files concurrently using async workers
4. **Streaming**: Use chunked processing with overlapping windows for better accuracy
5. **GPU Acceleration**: Support CUDA if GPU is available, fallback to CPU

### Docker Configuration

```dockerfile
# Multi-stage build for smaller image size
FROM python:3.11-slim as builder
# Install dependencies and download model weights
# ...

FROM python:3.11-slim
# Copy only necessary files from builder
# Expose port 8000
# Health check endpoint
```

### Environment Variables

- `WHISPER_MODEL_SIZE`: Model size (small/medium/large)
- `MAX_CONCURRENT_JOBS`: Maximum concurrent transcription jobs
- `MAX_FILE_SIZE_MB`: Maximum audio file size in MB
- `API_PORT`: Port for REST API (default: 8000)
- `LOG_LEVEL`: Logging level (DEBUG/INFO/WARNING/ERROR)

### Volume Mounts

- `/app/models`: Whisper model weights cache
- `/app/temp`: Temporary audio processing directory
- `/app/logs`: Application logs

This design provides a robust, performant, and testable Persian transcription API service that meets all requirements while maintaining simplicity and ease of deployment.
