# Persian Transcription API

A Dockerized REST API service for Persian (Farsi) speech transcription using OpenAI's Whisper model. This service provides both batch processing and real-time streaming transcription capabilities, running completely offline once deployed.

## Features

- **Batch Processing**: Upload complete audio files and receive transcription results asynchronously
- **Real-time Streaming**: Stream audio data via WebSocket and receive transcriptions in real-time
- **Offline Operation**: Runs completely locally without internet connectivity after initial setup
- **Multiple Formats**: Supports WAV, MP3, OGG, and M4A audio formats
- **Docker Containerized**: Easy deployment with Docker and docker-compose
- **Concurrent Processing**: Handles multiple transcription requests simultaneously
- **Automatic Health Checks**: Built-in health monitoring and capacity management

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
  - [Quick Start with Docker Compose](#quick-start-with-docker-compose)
  - [Manual Docker Build](#manual-docker-build)
  - [Local Development Setup](#local-development-setup)
- [Configuration](#configuration)
- [API Documentation](#api-documentation)
  - [Health Check](#health-check)
  - [Batch Transcription](#batch-transcription)
  - [Streaming Transcription](#streaming-transcription)
- [Usage Examples](#usage-examples)
  - [Using curl](#using-curl)
  - [Using Python](#using-python)
- [Performance and Resource Requirements](#performance-and-resource-requirements)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [License](#license)

## Requirements

### For Docker Deployment (Recommended)
- Docker 20.10+
- Docker Compose 2.0+
- 2-10 GB RAM (depending on model size)
- 4-8 CPU cores recommended

### For Local Development
- Python 3.11+
- FFmpeg
- 2-10 GB RAM (depending on model size)

## Installation

### Quick Start with Docker Compose

This is the easiest way to get started. The service will be ready in minutes.

1. **Clone the repository** (or download the project files)
   ```bash
   git clone <repository-url>
   cd persian-transcription-api
   ```

2. **(Optional) Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env to customize settings (model size, workers, etc.)
   ```

3. **Start the service**
   ```bash
   docker-compose up -d
   ```
   
   The first run will download the Whisper model (~1-5 GB depending on size), which may take several minutes.

4. **Verify the service is running**
   ```bash
   curl http://localhost:8000/api/v1/health
   ```
   
   Expected response:
   ```json
   {
     "status": "healthy",
     "model_loaded": true,
     "model_size": "medium"
   }
   ```

5. **View logs**
   ```bash
   docker-compose logs -f
   ```

6. **Stop the service**
   ```bash
   docker-compose down
   ```

### Manual Docker Build

If you prefer to build and run the Docker container manually:

1. **Build the Docker image**
   
   Build with default settings (medium model):
   ```bash
   docker build -t persian-transcription-api:latest .
   ```
   
   Build with a specific Whisper model size:
   ```bash
   docker build --build-arg WHISPER_MODEL_SIZE=small -t persian-transcription-api:small .
   ```

2. **Run the container**
   
   Basic run:
   ```bash
   docker run -d \
     --name persian-transcription-api \
     -p 8000:8000 \
     -v $(pwd)/temp:/app/temp \
     -v $(pwd)/logs:/app/logs \
     persian-transcription-api:latest
   ```
   
   Run with custom configuration:
   ```bash
   docker run -d \
     --name persian-transcription-api \
     -p 8000:8000 \
     -e WHISPER_MODEL_SIZE=small \
     -e MAX_CONCURRENT_WORKERS=2 \
     -e LOG_LEVEL=DEBUG \
     -v $(pwd)/temp:/app/temp \
     -v $(pwd)/logs:/app/logs \
     persian-transcription-api:latest
   ```

3. **Check container status**
   ```bash
   docker ps
   docker logs persian-transcription-api
   ```

4. **Stop and remove the container**
   ```bash
   docker stop persian-transcription-api
   docker rm persian-transcription-api
   ```

### Local Development Setup

For development without Docker:

1. **Install FFmpeg**
   
   Ubuntu/Debian:
   ```bash
   sudo apt-get update
   sudo apt-get install ffmpeg
   ```
   
   macOS:
   ```bash
   brew install ffmpeg
   ```
   
   Windows:
   Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the API server**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. **Access the API**
   - API: http://localhost:8000
   - Interactive docs: http://localhost:8000/docs
   - Alternative docs: http://localhost:8000/redoc

## Configuration

The service can be configured using environment variables. All settings have sensible defaults.

### Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `WHISPER_MODEL_SIZE` | `medium` | Whisper model size: `tiny`, `base`, `small`, `medium`, `large` |
| `MAX_CONCURRENT_WORKERS` | `4` | Maximum concurrent transcription workers |
| `MAX_QUEUE_SIZE` | `100` | Maximum number of queued jobs |
| `MAX_FILE_SIZE_MB` | `500` | Maximum audio file size in MB |
| `API_PORT` | `8000` | API port (container internal) |
| `API_HOST` | `0.0.0.0` | API host address |
| `LOG_LEVEL` | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `JOB_CLEANUP_MAX_AGE_HOURS` | `24` | Hours before completed jobs are cleaned up |
| `STREAM_MIN_CHUNK_SIZE` | `102400` | Minimum chunk size for streaming (bytes) |
| `STREAM_MAX_BUFFER_SIZE` | `10485760` | Maximum buffer size for streaming (bytes) |

### Model Size Comparison

| Model | RAM | CPU Cores | Speed | Accuracy | Use Case |
|-------|-----|-----------|-------|----------|----------|
| `tiny` | 1 GB | 1-2 | Very Fast | Low | Quick testing |
| `base` | 1 GB | 1-2 | Fast | Low | Development |
| `small` | 2 GB | 2-4 | Moderate | Good | Balanced |
| `medium` | 5 GB | 4-8 | Moderate | Very Good | **Recommended for production** |
| `large` | 10 GB | 8+ | Slow | Excellent | High-accuracy requirements |

### Configuration Examples

**Development Setup** (fast iteration):
```bash
WHISPER_MODEL_SIZE=small
MAX_CONCURRENT_WORKERS=2
LOG_LEVEL=DEBUG
```

**Production Setup** (balanced):
```bash
WHISPER_MODEL_SIZE=medium
MAX_CONCURRENT_WORKERS=4
MAX_FILE_SIZE_MB=500
LOG_LEVEL=INFO
```

**High-Accuracy Setup** (best quality):
```bash
WHISPER_MODEL_SIZE=large
MAX_CONCURRENT_WORKERS=2
MAX_FILE_SIZE_MB=1000
LOG_LEVEL=INFO
```

**Resource-Constrained Setup** (low memory):
```bash
WHISPER_MODEL_SIZE=tiny
MAX_CONCURRENT_WORKERS=1
MAX_FILE_SIZE_MB=100
MAX_QUEUE_SIZE=10
```

## API Documentation

The API follows RESTful conventions and returns JSON responses. All endpoints are prefixed with `/api/v1`.

### Base URL

```
http://localhost:8000/api/v1
```

### Health Check

Check if the service is running and the model is loaded.

**Endpoint:** `GET /api/v1/health`

**Response:**
```json
{
  "status": "healthy",
  "model_loaded": true,
  "model_size": "medium"
}
```

**Status Codes:**
- `200 OK`: Service is healthy

**Example:**
```bash
curl http://localhost:8000/api/v1/health
```

### Capacity Check

Get current service capacity and load information.

**Endpoint:** `GET /api/v1/capacity`

**Response:**
```json
{
  "active_jobs": 2,
  "queued_jobs": 5,
  "max_workers": 4,
  "max_queue_size": 100,
  "available_capacity": 93,
  "at_capacity": false
}
```

**Status Codes:**
- `200 OK`: Capacity information retrieved
- `503 Service Unavailable`: Service not available

### Batch Transcription

Upload an audio file for asynchronous transcription.

#### Upload Audio File

**Endpoint:** `POST /api/v1/transcribe/batch`

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body: Audio file (field name: `audio_file`)

**Supported Formats:**
- WAV (audio/wav)
- MP3 (audio/mpeg)
- OGG (audio/ogg)
- M4A (audio/mp4, audio/x-m4a)

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending"
}
```

**Status Codes:**
- `200 OK`: File accepted, transcription started
- `400 Bad Request`: Invalid file or missing data
- `413 Payload Too Large`: File exceeds size limit
- `415 Unsupported Media Type`: Audio format not supported
- `503 Service Unavailable`: Service at capacity or not ready

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/transcribe/batch \
  -F "audio_file=@/path/to/audio.mp3"
```

#### Get Transcription Status

**Endpoint:** `GET /api/v1/transcribe/batch/{job_id}`

**Response (Processing):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "transcription": null,
  "error": null
}
```

**Response (Completed):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "transcription": "این یک متن نمونه به زبان فارسی است",
  "error": null
}
```

**Response (Failed):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "transcription": null,
  "error": "Audio file is corrupted or unreadable"
}
```

**Status Values:**
- `pending`: Job is queued, waiting to be processed
- `processing`: Job is currently being transcribed
- `completed`: Transcription finished successfully
- `failed`: Transcription failed with an error

**Status Codes:**
- `200 OK`: Job status retrieved
- `404 Not Found`: Job ID not found
- `503 Service Unavailable`: Service not available

**Example:**
```bash
curl http://localhost:8000/api/v1/transcribe/batch/550e8400-e29b-41d4-a716-446655440000
```

### Streaming Transcription

Real-time transcription via WebSocket connection.

**Endpoint:** `WebSocket /api/v1/transcribe/stream`

**Protocol:**
1. Client connects to WebSocket endpoint
2. Client sends audio chunks as binary data
3. Server processes chunks incrementally
4. Server sends partial transcription results as JSON messages
5. Client closes connection when done
6. Server sends final transcription before closing

**Message Format (Server → Client):**
```json
{
  "type": "partial",
  "text": "این یک متن",
  "timestamp": 1234567890.123
}
```

**Message Types:**
- `partial`: Intermediate transcription result
- `final`: Final transcription when connection closes
- `error`: Error occurred during processing

**Example WebSocket URL:**
```
ws://localhost:8000/api/v1/transcribe/stream
```

## Usage Examples

### Using curl

#### Batch Transcription

1. **Upload an audio file:**
   ```bash
   curl -X POST http://localhost:8000/api/v1/transcribe/batch \
     -F "audio_file=@audio.mp3" \
     -H "Accept: application/json"
   ```
   
   Response:
   ```json
   {
     "job_id": "550e8400-e29b-41d4-a716-446655440000",
     "status": "pending"
   }
   ```

2. **Check transcription status:**
   ```bash
   curl http://localhost:8000/api/v1/transcribe/batch/550e8400-e29b-41d4-a716-446655440000
   ```
   
   Response:
   ```json
   {
     "job_id": "550e8400-e29b-41d4-a716-446655440000",
     "status": "completed",
     "transcription": "این یک متن نمونه به زبان فارسی است",
     "error": null
   }
   ```

3. **Poll until complete:**
   ```bash
   #!/bin/bash
   JOB_ID="550e8400-e29b-41d4-a716-446655440000"
   
   while true; do
     RESPONSE=$(curl -s http://localhost:8000/api/v1/transcribe/batch/$JOB_ID)
     STATUS=$(echo $RESPONSE | jq -r '.status')
     
     echo "Status: $STATUS"
     
     if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
       echo $RESPONSE | jq '.'
       break
     fi
     
     sleep 2
   done
   ```

### Using Python

#### Batch Transcription

```python
import requests
import time
import json

# API base URL
BASE_URL = "http://localhost:8000/api/v1"

def transcribe_audio_file(file_path):
    """
    Transcribe an audio file using batch processing.
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        Transcription text or None if failed
    """
    # Upload the file
    with open(file_path, 'rb') as f:
        files = {'audio_file': f}
        response = requests.post(f"{BASE_URL}/transcribe/batch", files=files)
    
    if response.status_code != 200:
        print(f"Upload failed: {response.status_code}")
        print(response.json())
        return None
    
    # Get job ID
    job_data = response.json()
    job_id = job_data['job_id']
    print(f"Job created: {job_id}")
    
    # Poll for completion
    while True:
        response = requests.get(f"{BASE_URL}/transcribe/batch/{job_id}")
        
        if response.status_code != 200:
            print(f"Status check failed: {response.status_code}")
            return None
        
        status_data = response.json()
        status = status_data['status']
        
        print(f"Status: {status}")
        
        if status == 'completed':
            return status_data['transcription']
        elif status == 'failed':
            print(f"Transcription failed: {status_data['error']}")
            return None
        
        # Wait before polling again
        time.sleep(2)

# Example usage
if __name__ == "__main__":
    transcription = transcribe_audio_file("audio.mp3")
    
    if transcription:
        print("\nTranscription:")
        print(transcription)
```

#### Streaming Transcription

```python
import asyncio
import websockets
import json

async def stream_audio_file(file_path, chunk_size=4096):
    """
    Stream an audio file for real-time transcription.
    
    Args:
        file_path: Path to the audio file
        chunk_size: Size of chunks to send (bytes)
    """
    uri = "ws://localhost:8000/api/v1/transcribe/stream"
    
    async with websockets.connect(uri) as websocket:
        print("Connected to streaming endpoint")
        
        # Send audio chunks
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                
                await websocket.send(chunk)
                print(f"Sent {len(chunk)} bytes")
        
        print("Finished sending audio, waiting for results...")
        
        # Receive transcription results
        try:
            async for message in websocket:
                data = json.loads(message)
                
                if data['type'] == 'partial':
                    print(f"Partial: {data['text']}")
                elif data['type'] == 'final':
                    print(f"Final: {data['text']}")
                    break
                elif data['type'] == 'error':
                    print(f"Error: {data['text']}")
                    break
        except websockets.exceptions.ConnectionClosed:
            print("Connection closed")

# Example usage
if __name__ == "__main__":
    asyncio.run(stream_audio_file("audio.mp3"))
```

#### Advanced: Concurrent Batch Processing

```python
import requests
import concurrent.futures
import time

BASE_URL = "http://localhost:8000/api/v1"

def transcribe_file(file_path):
    """Transcribe a single file."""
    # Upload
    with open(file_path, 'rb') as f:
        response = requests.post(
            f"{BASE_URL}/transcribe/batch",
            files={'audio_file': f}
        )
    
    if response.status_code != 200:
        return file_path, None, f"Upload failed: {response.status_code}"
    
    job_id = response.json()['job_id']
    
    # Poll for completion
    while True:
        response = requests.get(f"{BASE_URL}/transcribe/batch/{job_id}")
        
        if response.status_code != 200:
            return file_path, None, f"Status check failed"
        
        data = response.json()
        
        if data['status'] == 'completed':
            return file_path, data['transcription'], None
        elif data['status'] == 'failed':
            return file_path, None, data['error']
        
        time.sleep(2)

def transcribe_multiple_files(file_paths, max_workers=4):
    """
    Transcribe multiple files concurrently.
    
    Args:
        file_paths: List of audio file paths
        max_workers: Maximum concurrent uploads
        
    Returns:
        Dictionary mapping file paths to transcriptions
    """
    results = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all files
        future_to_file = {
            executor.submit(transcribe_file, fp): fp 
            for fp in file_paths
        }
        
        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_file):
            file_path = future_to_file[future]
            
            try:
                path, transcription, error = future.result()
                
                if error:
                    print(f"❌ {path}: {error}")
                    results[path] = None
                else:
                    print(f"✓ {path}: Success")
                    results[path] = transcription
            except Exception as e:
                print(f"❌ {file_path}: {e}")
                results[file_path] = None
    
    return results

# Example usage
if __name__ == "__main__":
    files = ["audio1.mp3", "audio2.mp3", "audio3.mp3"]
    results = transcribe_multiple_files(files)
    
    for file_path, transcription in results.items():
        print(f"\n{file_path}:")
        print(transcription or "Failed")
```

## Performance and Resource Requirements

### Model Performance Characteristics

| Model | Download Size | RAM Usage | Relative Speed | Persian Accuracy |
|-------|--------------|-----------|----------------|------------------|
| tiny | ~75 MB | ~1 GB | 32x realtime | Fair |
| base | ~150 MB | ~1 GB | 16x realtime | Good |
| small | ~500 MB | ~2 GB | 6x realtime | Very Good |
| medium | ~1.5 GB | ~5 GB | 2x realtime | Excellent ⭐ |
| large | ~3 GB | ~10 GB | 1x realtime | Best |

**Note:** "Realtime" means processing speed relative to audio duration. 2x realtime = 1 minute of audio processed in 30 seconds.

### Recommended System Requirements

**Minimum (tiny/base model):**
- 2 CPU cores
- 2 GB RAM
- 5 GB disk space

**Recommended (medium model):**
- 4-8 CPU cores
- 8 GB RAM
- 10 GB disk space

**High-Performance (large model):**
- 8+ CPU cores
- 16 GB RAM
- 15 GB disk space

### Concurrent Processing

The service can process multiple files simultaneously based on `MAX_CONCURRENT_WORKERS`:

- Each worker processes one file at a time
- Workers share the same model instance (memory efficient)
- Additional requests are queued up to `MAX_QUEUE_SIZE`
- Requests beyond queue limit receive 503 errors

**Example:** With 4 workers and 100 queue size:
- 4 files processing simultaneously
- Up to 100 files waiting in queue
- 101st request gets rejected with 503

## Troubleshooting

### Common Issues

#### Service Won't Start

**Symptom:** Container exits immediately or health check fails

**Solutions:**
1. Check logs: `docker-compose logs`
2. Verify port 8000 is not in use: `lsof -i :8000` (Unix) or `netstat -ano | findstr :8000` (Windows)
3. Ensure sufficient disk space for model download (3-5 GB)
4. Check Docker has enough memory allocated (Docker Desktop → Settings → Resources)

#### Out of Memory Errors

**Symptom:** Container crashes or transcription fails with memory errors

**Solutions:**
1. Use a smaller model: `WHISPER_MODEL_SIZE=small` or `tiny`
2. Reduce concurrent workers: `MAX_CONCURRENT_WORKERS=2` or `1`
3. Reduce max file size: `MAX_FILE_SIZE_MB=100`
4. Increase Docker memory limit in `docker-compose.yml`:
   ```yaml
   services:
     api:
       deploy:
         resources:
           limits:
             memory: 8G
   ```

#### Slow Transcription

**Symptom:** Transcription takes too long

**Solutions:**
1. Use a smaller/faster model: `WHISPER_MODEL_SIZE=small`
2. Reduce concurrent workers to avoid CPU contention: `MAX_CONCURRENT_WORKERS=2`
3. Ensure no other CPU-intensive processes are running
4. Consider GPU acceleration (requires CUDA-enabled Docker and GPU)

#### Model Download Fails

**Symptom:** First run fails to download model

**Solutions:**
1. Ensure internet connection is available during first run
2. Check firewall/proxy settings
3. Manually download model and mount as volume
4. Clear Docker volumes and retry: `docker-compose down -v && docker-compose up`

#### Port Already in Use

**Symptom:** Error binding to port 8000

**Solutions:**
1. Change port in `.env`: `API_PORT=8080`
2. Or in docker-compose.yml: `ports: - "8080:8000"`
3. Stop conflicting service: `lsof -ti:8000 | xargs kill` (Unix)

#### Unsupported Format Error

**Symptom:** 415 error even with supported format

**Solutions:**
1. Verify file is not corrupted: Try playing it in a media player
2. Check file extension matches content: Use `file` command (Unix)
3. Convert to WAV format first: `ffmpeg -i input.mp3 output.wav`
4. Ensure Content-Type header is correct in request

#### Job Not Found (404)

**Symptom:** Status check returns 404 for valid job ID

**Solutions:**
1. Job may have been cleaned up (older than `JOB_CLEANUP_MAX_AGE_HOURS`)
2. Service may have restarted (jobs are in-memory only)
3. Verify job ID is correct (copy-paste to avoid typos)

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
# In .env file
LOG_LEVEL=DEBUG

# Or when running Docker
docker run -e LOG_LEVEL=DEBUG ...
```

View logs:
```bash
# Docker Compose
docker-compose logs -f

# Docker
docker logs -f persian-transcription-api

# Local development
# Logs are printed to console
```

### Getting Help

If you encounter issues not covered here:

1. Check the logs for error messages
2. Verify your configuration matches the examples
3. Test with a small, known-good audio file
4. Try the smallest model (tiny) to rule out resource issues
5. Check Docker/system resources (CPU, RAM, disk)

## Development

### Project Structure

```
persian-transcription-api/
├── app/                          # Main application code
│   ├── __init__.py
│   ├── main.py                   # FastAPI application entry point
│   ├── api_models.py             # Pydantic models for API
│   ├── audio_processor.py        # Audio format handling
│   ├── config.py                 # Configuration management
│   ├── job_manager.py            # Job state management
│   ├── logging_config.py         # Structured logging setup
│   ├── models.py                 # Data models
│   ├── transcription_service.py  # Orchestration layer
│   └── whisper_engine.py         # Whisper model wrapper
├── tests/                        # Test suite
│   ├── unit/                     # Unit tests
│   ├── property/                 # Property-based tests
│   └── integration/              # Integration tests
├── docker/                       # Docker configuration
├── logs/                         # Application logs
├── temp/                         # Temporary audio files
├── .env.example                  # Example environment config
├── .gitignore                    # Git ignore rules
├── docker-compose.yml            # Docker Compose configuration
├── Dockerfile                    # Docker image definition
├── pyproject.toml                # Project metadata
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

### Running Tests

```bash
# Install development dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test categories
pytest tests/unit/                # Unit tests only
pytest -m property_test           # Property-based tests only
pytest tests/integration/         # Integration tests only

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_audio_processor.py
```

### API Documentation

The service provides interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

These are automatically generated from the FastAPI application and provide:
- Complete endpoint documentation
- Request/response schemas
- Interactive testing interface
- Example requests and responses

### Code Style

The project follows Python best practices:
- PEP 8 style guide
- Type hints for all functions
- Docstrings for all public APIs
- Structured logging with context

### Contributing

When contributing to this project:

1. Write tests for new features
2. Ensure all tests pass: `pytest`
3. Follow existing code style
4. Update documentation as needed
5. Add type hints to new code

## License

(License information to be added)

---

## Quick Reference

### Essential Commands

```bash
# Start service
docker-compose up -d

# Stop service
docker-compose down

# View logs
docker-compose logs -f

# Check health
curl http://localhost:8000/api/v1/health

# Transcribe a file
curl -X POST http://localhost:8000/api/v1/transcribe/batch \
  -F "audio_file=@audio.mp3"

# Check status
curl http://localhost:8000/api/v1/transcribe/batch/{job_id}
```

### Key URLs

- API Base: http://localhost:8000/api/v1
- Health Check: http://localhost:8000/api/v1/health
- API Docs: http://localhost:8000/docs
- WebSocket: ws://localhost:8000/api/v1/transcribe/stream

### Default Configuration

- Model: medium
- Workers: 4
- Queue Size: 100
- Max File Size: 500 MB
- Port: 8000
- Log Level: INFO
