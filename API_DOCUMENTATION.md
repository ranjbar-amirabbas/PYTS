# Persian Transcription API Documentation

## Overview

The Persian Transcription API provides comprehensive, automatically generated API documentation through FastAPI's built-in OpenAPI support. This document explains how to access and use the API documentation.

## Accessing the Documentation

Once the service is running, you can access the interactive API documentation through two interfaces:

### 1. Swagger UI (Recommended)

**URL:** `http://localhost:8000/docs`

The Swagger UI provides an interactive interface where you can:
- Browse all available endpoints
- View detailed request/response schemas
- Try out API calls directly from the browser
- See example requests and responses
- View error codes and their meanings

**Features:**
- Interactive "Try it out" buttons for each endpoint
- Automatic request validation
- Real-time response display
- Code examples in multiple languages

### 2. ReDoc

**URL:** `http://localhost:8000/redoc`

ReDoc provides a clean, three-panel documentation interface:
- Left panel: Navigation menu
- Center panel: Detailed endpoint documentation
- Right panel: Request/response examples

**Features:**
- Clean, readable layout
- Comprehensive schema documentation
- Search functionality
- Downloadable OpenAPI specification

### 3. OpenAPI JSON Schema

**URL:** `http://localhost:8000/openapi.json`

Download the raw OpenAPI 3.0 specification in JSON format for:
- Generating client libraries
- Importing into API testing tools (Postman, Insomnia)
- Custom documentation generation
- API contract validation

## API Endpoints

### Health and Monitoring

#### GET /api/v1/health
Check service health status and model readiness.

**Response:**
```json
{
  "status": "healthy",
  "model_loaded": true,
  "model_size": "medium"
}
```

#### GET /api/v1/capacity
Get current service capacity and load information.

**Response:**
```json
{
  "active_jobs": 2,
  "queued_jobs": 1,
  "max_workers": 4,
  "max_queue_size": 10,
  "available_capacity": 7,
  "at_capacity": false
}
```

### Batch Transcription

#### POST /api/v1/transcribe/batch
Upload an audio file for batch transcription.

**Request:**
- Content-Type: `multipart/form-data`
- Body: `audio_file` (file)

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

**Example (curl):**
```bash
curl -X POST http://localhost:8000/api/v1/transcribe/batch \
     -F "audio_file=@sample.mp3"
```

**Example (Python):**
```python
import requests

with open("audio.wav", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/v1/transcribe/batch",
        files={"audio_file": f}
    )

data = response.json()
job_id = data["job_id"]
print(f"Job created: {job_id}")
```

#### GET /api/v1/transcribe/batch/{job_id}
Get the status and result of a batch transcription job.

**Response (Completed):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "transcription": "سلام، این یک نمونه متن فارسی است.",
  "error": null
}
```

**Job Status Values:**
- `pending`: Job is queued and waiting to be processed
- `processing`: Job is currently being transcribed
- `completed`: Transcription finished successfully
- `failed`: Transcription failed

**Example (curl):**
```bash
curl http://localhost:8000/api/v1/transcribe/batch/550e8400-e29b-41d4-a716-446655440000
```

**Example (Python with polling):**
```python
import requests
import time

job_id = "550e8400-e29b-41d4-a716-446655440000"

# Poll until completed or failed
while True:
    response = requests.get(
        f"http://localhost:8000/api/v1/transcribe/batch/{job_id}"
    )
    data = response.json()
    
    if data["status"] == "completed":
        print(f"Transcription: {data['transcription']}")
        break
    elif data["status"] == "failed":
        print(f"Error: {data['error']}")
        break
    else:
        print(f"Status: {data['status']}")
        time.sleep(2)
```

### Streaming Transcription

#### WebSocket /api/v1/transcribe/stream
Real-time streaming transcription via WebSocket.

**Protocol:**
1. Connect to WebSocket endpoint
2. Send audio chunks as binary data
3. Receive partial transcription results as JSON
4. Close connection to finalize

**Message Format (Server to Client):**
```json
{
  "type": "partial" | "final" | "error",
  "text": "transcribed text in Persian",
  "timestamp": 1234567890.123
}
```

**Example (Python with websockets):**
```python
import asyncio
import websockets
import json

async def stream_audio():
    uri = "ws://localhost:8000/api/v1/transcribe/stream"
    
    async with websockets.connect(uri) as websocket:
        # Send audio file in chunks
        with open("audio.wav", "rb") as f:
            while chunk := f.read(4096):
                await websocket.send(chunk)
        
        # Close sending side to signal end of audio
        await websocket.send(b"")
        
        # Receive transcription results
        async for message in websocket:
            data = json.loads(message)
            print(f"{data['type']}: {data['text']}")
            
            if data['type'] == 'final':
                break

asyncio.run(stream_audio())
```

**Example (JavaScript):**
```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/transcribe/stream');

ws.onopen = () => {
    // Send audio chunks
    fetch('audio.mp3')
        .then(response => response.arrayBuffer())
        .then(buffer => {
            const chunkSize = 4096;
            for (let i = 0; i < buffer.byteLength; i += chunkSize) {
                const chunk = buffer.slice(i, i + chunkSize);
                ws.send(chunk);
            }
            ws.close();
        });
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log(`${data.type}: ${data.text}`);
};

ws.onerror = (error) => {
    console.error('WebSocket error:', error);
};
```

## Error Handling

All API errors follow a consistent format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error description",
    "details": "Additional context (optional)"
  }
}
```

### Common Error Codes

#### 400 Bad Request
- `MISSING_FILE`: No audio file provided
- `INVALID_INPUT`: Invalid request data
- `VALIDATION_ERROR`: Request validation failed

#### 404 Not Found
- `JOB_NOT_FOUND`: Job ID not found
- `NOT_FOUND`: Resource not found

#### 413 Payload Too Large
- `FILE_TOO_LARGE`: File size exceeds maximum limit (500 MB)

#### 415 Unsupported Media Type
- `UNSUPPORTED_FORMAT`: Audio format not supported

#### 503 Service Unavailable
- `SERVICE_UNAVAILABLE`: Transcription service is not available
- `AT_CAPACITY`: Server is at capacity, retry later

#### 500 Internal Server Error
- `INTERNAL_ERROR`: Unexpected server error

## Request/Response Schemas

### BatchTranscribeResponse
```json
{
  "job_id": "string",
  "status": "string"
}
```

### BatchStatusResponse
```json
{
  "job_id": "string",
  "status": "pending" | "processing" | "completed" | "failed",
  "transcription": "string | null",
  "error": "string | null"
}
```

### HealthResponse
```json
{
  "status": "string",
  "model_loaded": "boolean",
  "model_size": "string"
}
```

### StreamTranscriptionMessage
```json
{
  "type": "partial" | "final" | "error",
  "text": "string",
  "timestamp": "number"
}
```

## Best Practices

### Batch Transcription
1. **Check capacity** before submitting large batches
2. **Implement polling** with appropriate intervals (1-2 seconds for short clips, 5-10 seconds for long files)
3. **Handle 503 errors** with exponential backoff retry strategy
4. **Validate audio format** before uploading to avoid 415 errors
5. **Monitor file size** to stay under 500 MB limit

### Streaming Transcription
1. **Send consistent chunk sizes** (4096-8192 bytes recommended)
2. **Handle partial results** as they may change with more context
3. **Implement error handling** for connection failures
4. **Close connection properly** to receive final transcription
5. **Monitor buffer limits** to avoid buffer overflow errors

### Performance Optimization
1. **Use batch processing** for pre-recorded audio (faster than streaming)
2. **Reuse connections** when possible
3. **Implement client-side caching** for repeated requests
4. **Monitor capacity endpoint** to avoid rejected requests
5. **Use appropriate polling intervals** to balance responsiveness and server load

## Testing the API

### Using Swagger UI
1. Navigate to `http://localhost:8000/docs`
2. Click on any endpoint to expand it
3. Click "Try it out" button
4. Fill in required parameters
5. Click "Execute" to send the request
6. View the response below

### Using curl
See the examples in each endpoint section above.

### Using Postman
1. Import the OpenAPI specification from `http://localhost:8000/openapi.json`
2. Postman will automatically create a collection with all endpoints
3. Configure environment variables (base URL, etc.)
4. Test endpoints directly from Postman

### Using Python requests
See the Python examples in each endpoint section above.

## Additional Resources

- **README.md**: General setup and usage instructions
- **Swagger UI**: `http://localhost:8000/docs` (interactive documentation)
- **ReDoc**: `http://localhost:8000/redoc` (alternative documentation view)
- **OpenAPI Spec**: `http://localhost:8000/openapi.json` (machine-readable specification)

## Requirements Validation

This API documentation validates the following requirements:

- **5.1**: REST API exposes endpoints for batch audio upload ✓
- **5.2**: REST API exposes endpoints for streaming audio processing ✓
- **5.3**: REST API exposes endpoints for retrieving transcription results ✓
- **5.4**: REST API exposes endpoints for checking service health and status ✓
- **5.5**: REST API returns responses in JSON format ✓
- **5.6**: REST API returns appropriate HTTP status codes and error messages ✓
- **5.7**: REST API follows RESTful conventions ✓

All endpoints are fully documented with:
- Detailed descriptions
- Request/response schemas
- Example requests and responses
- Error codes and handling
- Usage examples in multiple languages
