"""
FastAPI application for Persian Transcription API.

This module initializes the FastAPI application with CORS configuration
and exception handlers for consistent error responses.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, AsyncGenerator, Optional
import json
import time

from app.api_models import BatchTranscribeResponse, BatchStatusResponse, HealthResponse, StreamTranscriptionMessage
from app.transcription_service import TranscriptionService
from app.audio_processor import UnsupportedFormatError
from app.config import settings
from app.logging_config import setup_logging, get_logger, log_with_context

# Configure structured logging
setup_logging(
    log_level=settings.log_level.value,
    use_json=True
)
logger = get_logger(__name__)

# Configuration constants from settings
MAX_FILE_SIZE_MB = settings.max_file_size_mb
MAX_FILE_SIZE_BYTES = settings.get_max_file_size_bytes()
SUPPORTED_FORMATS = ["audio/wav", "audio/mpeg", "audio/ogg", "audio/mp4", "audio/x-m4a"]

# Global transcription service instance
transcription_service: Optional[TranscriptionService] = None


# Lifespan context manager for startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage application lifespan events.
    
    Handles initialization on startup and cleanup on shutdown.
    """
    global transcription_service
    
    # Startup
    logger.info("Persian Transcription API starting up...")
    logger.info(settings.display())
    
    # Initialize transcription service
    try:
        transcription_service = TranscriptionService(
            max_workers=settings.max_concurrent_workers,
            max_queue_size=settings.max_queue_size
        )
        # Note: Model initialization is deferred to first request to speed up startup
        # transcription_service.initialize()
        logger.info("Transcription service created (model will load on first request)")
    except Exception as e:
        logger.error(f"Failed to create transcription service: {e}")
        transcription_service = None
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Persian Transcription API shutting down...")
    
    # Cleanup transcription service
    if transcription_service:
        try:
            transcription_service.shutdown()
            logger.info("Transcription service shutdown complete")
        except Exception as e:
            logger.error(f"Error during transcription service shutdown: {e}")
    
    logger.info("Application shutdown complete")


# Initialize FastAPI application with lifespan
app = FastAPI(
    title="Persian Transcription API",
    description="""
    A REST API service for Persian (Farsi) speech-to-text transcription using OpenAI's Whisper model.
    
    ## Features
    
    * **Batch Processing**: Upload complete audio files and retrieve transcription results asynchronously
    * **Real-time Streaming**: Stream audio data via WebSocket for live transcription
    * **Multiple Formats**: Support for WAV, MP3, OGG, and M4A audio formats
    * **Offline Operation**: Runs completely locally without internet connectivity
    * **Persian Optimized**: Uses Whisper model specifically configured for Persian language
    
    ## Supported Audio Formats
    
    * WAV (audio/wav)
    * MP3 (audio/mpeg)
    * OGG (audio/ogg)
    * M4A (audio/mp4, audio/x-m4a)
    
    ## API Workflow
    
    ### Batch Transcription
    1. Upload audio file to `POST /api/v1/transcribe/batch`
    2. Receive job_id in response
    3. Poll `GET /api/v1/transcribe/batch/{job_id}` to check status
    4. Retrieve transcription when status is "completed"
    
    ### Streaming Transcription
    1. Connect to WebSocket endpoint `/api/v1/transcribe/stream`
    2. Send audio chunks as binary data
    3. Receive partial transcription results in real-time
    4. Close connection to finalize and receive final transcription
    
    ## Rate Limits and Capacity
    
    The service processes requests using a worker pool with configurable concurrency limits.
    When at capacity, the API returns 503 errors. Check `/api/v1/capacity` for current load.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    contact={
        "name": "Persian Transcription API",
        "url": "https://github.com/yourusername/persian-transcription-api",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
)

# Configure CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local development
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)


# Request/Response logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Middleware to log all HTTP requests and responses.
    
    Logs request details (method, URL, client) and response details
    (status code, processing time) for debugging and monitoring.
    """
    # Log incoming request
    try:
        log_with_context(
            logger,
            "info",
            "Incoming request",
            method=request.method,
            url=str(request.url),
            client=request.client.host if request.client else "unknown",
            path=request.url.path
        )
    except Exception:
        # If logging fails, don't break the request
        pass
    
    # Process request and measure time
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    # Log response
    try:
        log_with_context(
            logger,
            "info",
            "Request completed",
            method=request.method,
            url=str(request.url),
            status_code=response.status_code,
            process_time_ms=round(process_time * 1000, 2)
        )
    except Exception:
        # If logging fails, don't break the response
        pass
    
    return response


# Custom exception handlers for consistent error responses

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, 
    exc: RequestValidationError
) -> JSONResponse:
    """
    Handle request validation errors with consistent error format.
    
    Returns 400 Bad Request with error details.
    """
    log_with_context(
        logger,
        "warning",
        "Validation error",
        url=str(request.url),
        method=request.method,
        errors=exc.errors()
    )
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request data",
                "details": exc.errors()
            }
        }
    )


@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(
    request: Request,
    exc: ValidationError
) -> JSONResponse:
    """
    Handle Pydantic validation errors with consistent error format.
    
    Returns 400 Bad Request with error details.
    """
    log_with_context(
        logger,
        "warning",
        "Pydantic validation error",
        url=str(request.url),
        method=request.method,
        errors=exc.errors()
    )
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid data format",
                "details": exc.errors()
            }
        }
    )


@app.exception_handler(ValueError)
async def value_error_exception_handler(
    request: Request,
    exc: ValueError
) -> JSONResponse:
    """
    Handle ValueError exceptions with consistent error format.
    
    Returns 400 Bad Request for client errors.
    """
    log_with_context(
        logger,
        "warning",
        "ValueError",
        url=str(request.url),
        method=request.method,
        error=exc
    )
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": {
                "code": "INVALID_INPUT",
                "message": str(exc),
                "details": None
            }
        }
    )


@app.exception_handler(FileNotFoundError)
async def file_not_found_exception_handler(
    request: Request,
    exc: FileNotFoundError
) -> JSONResponse:
    """
    Handle FileNotFoundError exceptions with consistent error format.
    
    Returns 404 Not Found.
    """
    log_with_context(
        logger,
        "warning",
        "FileNotFoundError",
        url=str(request.url),
        method=request.method,
        error=exc
    )
    
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": {
                "code": "NOT_FOUND",
                "message": str(exc),
                "details": None
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """
    Handle all other exceptions with consistent error format.
    
    Returns 500 Internal Server Error for unexpected errors.
    """
    log_with_context(
        logger,
        "error",
        "Unexpected error",
        url=str(request.url),
        method=request.method,
        error=exc
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": str(exc)
            }
        }
    )


# Health check endpoint (basic implementation)
@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Check service health status",
    responses={
        200: {
            "description": "Service is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "model_loaded": True,
                        "model_size": "medium"
                    }
                }
            }
        }
    }
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint to verify service status and model readiness.
    
    This endpoint provides information about the service health and whether
    the Whisper transcription model is loaded and ready to process requests.
    
    **Use this endpoint to:**
    - Verify the service is running
    - Check if the model is loaded before sending transcription requests
    - Monitor service availability in production
    
    **Response Fields:**
    - `status`: Overall service health ("healthy" or "unhealthy")
    - `model_loaded`: Boolean indicating if the Whisper model is loaded
    - `model_size`: Size of the loaded model (e.g., "small", "medium", "large")
    
    **Note:** The model is loaded lazily on the first transcription request
    to speed up service startup. If `model_loaded` is false, the first
    transcription request will trigger model initialization.
    
    Returns:
        HealthResponse: Service health status including model readiness
    
    Example:
        ```bash
        curl http://localhost:8000/api/v1/health
        ```
        
        Response:
        ```json
        {
            "status": "healthy",
            "model_loaded": true,
            "model_size": "medium"
        }
        ```
    """
    model_loaded = False
    model_size = "not_loaded"
    
    if transcription_service:
        model_loaded = transcription_service.is_ready()
        if model_loaded:
            model_size = transcription_service.whisper_engine.model_size
    
    return HealthResponse(
        status="healthy",
        model_loaded=model_loaded,
        model_size=model_size
    )


@app.get(
    "/api/v1/capacity",
    tags=["Health"],
    summary="Get service capacity and load information",
    responses={
        200: {
            "description": "Current capacity information",
            "content": {
                "application/json": {
                    "example": {
                        "active_jobs": 2,
                        "queued_jobs": 1,
                        "max_workers": 4,
                        "max_queue_size": 10,
                        "available_capacity": 7,
                        "at_capacity": False
                    }
                }
            }
        },
        503: {
            "description": "Service not available",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "SERVICE_UNAVAILABLE",
                            "message": "Transcription service is not available",
                            "details": None
                        }
                    }
                }
            }
        }
    }
)
async def get_capacity() -> dict:
    """
    Get current service capacity and load information.
    
    This endpoint provides real-time information about the service's processing
    capacity, including active jobs, queued jobs, and available capacity.
    
    **Use this endpoint to:**
    - Monitor service load before submitting transcription requests
    - Implement client-side rate limiting or backoff strategies
    - Track service utilization for capacity planning
    
    **Response Fields:**
    - `active_jobs`: Number of transcription jobs currently being processed
    - `queued_jobs`: Number of jobs waiting in the queue
    - `max_workers`: Maximum number of concurrent workers
    - `max_queue_size`: Maximum number of jobs that can be queued
    - `available_capacity`: Number of additional jobs that can be queued
    - `at_capacity`: Boolean indicating if the service is at full capacity
    
    **Capacity Management:**
    - When `at_capacity` is true, new transcription requests will be rejected with 503 errors
    - Available capacity = max_queue_size - queued_jobs
    - Total capacity = max_workers + max_queue_size
    
    Returns:
        Dictionary with capacity information
    
    Raises:
        HTTPException 503: Service not available
    
    Example:
        ```bash
        curl http://localhost:8000/api/v1/capacity
        ```
        
        Response:
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
    """
    if not transcription_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "Transcription service is not available",
                    "details": None
                }
            }
        )
    
    capacity_info = transcription_service.get_capacity_info()
    capacity_info["at_capacity"] = transcription_service.is_at_capacity()
    
    return capacity_info


# Batch transcription endpoints

@app.post(
    "/api/v1/transcribe/batch",
    response_model=BatchTranscribeResponse,
    status_code=status.HTTP_200_OK,
    tags=["Transcription"],
    summary="Upload audio file for batch transcription",
    responses={
        200: {
            "description": "Transcription job created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "job_id": "550e8400-e29b-41d4-a716-446655440000",
                        "status": "pending"
                    }
                }
            }
        },
        400: {
            "description": "Invalid request (missing file, corrupted file)",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "MISSING_FILE",
                            "message": "No audio file provided",
                            "details": None
                        }
                    }
                }
            }
        },
        413: {
            "description": "File size exceeds maximum limit",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "FILE_TOO_LARGE",
                            "message": "File size exceeds maximum limit of 500 MB",
                            "details": None
                        }
                    }
                }
            }
        },
        415: {
            "description": "Unsupported audio format",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "UNSUPPORTED_FORMAT",
                            "message": "Audio format not supported. Supported formats: WAV, MP3, OGG, M4A",
                            "details": "Received content type: audio/flac"
                        }
                    }
                }
            }
        },
        503: {
            "description": "Service unavailable or at capacity",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "AT_CAPACITY",
                            "message": "Server is at capacity. Please retry later.",
                            "details": {
                                "active_jobs": 4,
                                "queued_jobs": 10,
                                "max_workers": 4
                            }
                        }
                    }
                }
            }
        }
    }
)
async def create_batch_transcription(
    audio_file: UploadFile = File(
        ...,
        description="Audio file to transcribe (WAV, MP3, OGG, or M4A format)"
    )
) -> BatchTranscribeResponse:
    """
    Upload an audio file for batch transcription.
    
    This endpoint accepts an audio file in a supported format and returns a job ID
    for tracking the transcription progress. The transcription is processed
    asynchronously using a worker pool.
    
    **Supported Formats:**
    - WAV (audio/wav)
    - MP3 (audio/mpeg)
    - OGG (audio/ogg)
    - M4A (audio/mp4, audio/x-m4a)
    
    **File Size Limits:**
    - Maximum file size: 500 MB (configurable via MAX_FILE_SIZE_MB)
    - No arbitrary duration limits - processes short clips to long recordings
    
    **Processing Workflow:**
    1. Upload audio file to this endpoint
    2. Receive job_id and status "pending" in response
    3. Poll GET /api/v1/transcribe/batch/{job_id} to check status
    4. Status transitions: pending → processing → completed (or failed)
    5. Retrieve transcription text when status is "completed"
    
    **Capacity Management:**
    - If the service is at capacity (queue is full), returns 503 error
    - Check /api/v1/capacity endpoint before submitting to avoid rejections
    - Implement exponential backoff retry strategy for 503 errors
    
    **Model Initialization:**
    - The Whisper model is loaded lazily on the first transcription request
    - First request may take longer due to model initialization
    - Subsequent requests use the cached model for faster processing
    
    Args:
        audio_file: The audio file to transcribe (multipart/form-data)
    
    Returns:
        BatchTranscribeResponse: Job ID and initial status ("pending")
    
    Raises:
        HTTPException 400: Invalid file format or corrupted file
        HTTPException 413: File size exceeds maximum limit (500 MB)
        HTTPException 415: Unsupported audio format
        HTTPException 503: Service not ready or at capacity
    
    Example (curl):
        ```bash
        curl -X POST http://localhost:8000/api/v1/transcribe/batch \\
             -F "audio_file=@sample.mp3"
        ```
        
        Response:
        ```json
        {
            "job_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "pending"
        }
        ```
    
    Example (Python):
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
    """
    # Check if service is available
    if not transcription_service:
        logger.error("Transcription service not available")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "Transcription service is not available",
                    "details": None
                }
            }
        )
    
    # Initialize model on first request if not already done
    if not transcription_service.is_ready():
        try:
            logger.info("Initializing transcription model on first request...")
            transcription_service.initialize()
        except Exception as e:
            logger.error(f"Failed to initialize transcription service: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": {
                        "code": "SERVICE_UNAVAILABLE",
                        "message": "Transcription service is initializing. Please retry in a few moments.",
                        "details": str(e)
                    }
                }
            )
    
    # Check if service is at capacity
    if transcription_service.is_at_capacity():
        capacity_info = transcription_service.get_capacity_info()
        logger.warning(
            f"Service at capacity. Active: {capacity_info['active_jobs']}, "
            f"Queued: {capacity_info['queued_jobs']}"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "AT_CAPACITY",
                    "message": "Server is at capacity. Please retry later.",
                    "details": {
                        "active_jobs": capacity_info['active_jobs'],
                        "queued_jobs": capacity_info['queued_jobs'],
                        "max_workers": capacity_info['max_workers']
                    }
                }
            }
        )
    
    # Validate file is provided
    if not audio_file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "MISSING_FILE",
                    "message": "No audio file provided",
                    "details": None
                }
            }
        )
    
    # Validate content type
    content_type = audio_file.content_type
    if content_type not in SUPPORTED_FORMATS:
        logger.warning(f"Unsupported content type: {content_type}")
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "error": {
                    "code": "UNSUPPORTED_FORMAT",
                    "message": "Audio format not supported. Supported formats: WAV, MP3, OGG, M4A",
                    "details": f"Received content type: {content_type}"
                }
            }
        )
    
    # Save uploaded file to temporary location
    temp_file = None
    try:
        # Create temporary file
        suffix = Path(audio_file.filename or "audio").suffix
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp_path = temp_file.name
        
        # Read and validate file size
        file_size = 0
        chunk_size = 1024 * 1024  # 1 MB chunks
        
        while True:
            chunk = await audio_file.read(chunk_size)
            if not chunk:
                break
            
            file_size += len(chunk)
            
            # Check file size limit
            if file_size > MAX_FILE_SIZE_BYTES:
                temp_file.close()
                Path(temp_path).unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail={
                        "error": {
                            "code": "FILE_TOO_LARGE",
                            "message": f"File size exceeds maximum limit of {MAX_FILE_SIZE_MB} MB",
                            "details": None
                        }
                    }
                )
            
            temp_file.write(chunk)
        
        temp_file.close()
        
        log_with_context(
            logger,
            "info",
            "Received audio file",
            file_name=audio_file.filename,
            file_size=file_size,
            content_type=content_type
        )
        
        # Submit for transcription
        try:
            job_id = transcription_service.transcribe_batch(temp_path)
            log_with_context(
                logger,
                "info",
                "Created batch transcription job",
                job_id=job_id,
                file_path=temp_path,
                file_size=file_size
            )
            
            return BatchTranscribeResponse(
                job_id=job_id,
                status="pending"
            )
        
        except UnsupportedFormatError as e:
            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)
            log_with_context(
                logger,
                "warning",
                "Unsupported format error",
                file_path=temp_path,
                error=e
            )
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail={
                    "error": {
                        "code": "UNSUPPORTED_FORMAT",
                        "message": str(e),
                        "details": None
                    }
                }
            )
        
        except FileNotFoundError as e:
            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)
            log_with_context(
                logger,
                "error",
                "File not found error",
                file_path=temp_path,
                error=e
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "FILE_NOT_FOUND",
                        "message": "Audio file could not be read",
                        "details": str(e)
                    }
                }
            )
        
        except RuntimeError as e:
            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)
            # Check if it's a capacity error
            if "at capacity" in str(e).lower():
                log_with_context(
                    logger,
                    "warning",
                    "Service at capacity",
                    error=e
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "error": {
                            "code": "AT_CAPACITY",
                            "message": str(e),
                            "details": None
                        }
                    }
                )
            else:
                log_with_context(
                    logger,
                    "error",
                    "Runtime error",
                    error=e
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={
                        "error": {
                            "code": "INTERNAL_ERROR",
                            "message": str(e),
                            "details": None
                        }
                    }
                )
        
        except Exception as e:
            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)
            log_with_context(
                logger,
                "error",
                "Error creating transcription job",
                file_path=temp_path,
                error=e
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "Failed to create transcription job",
                        "details": str(e)
                    }
                }
            )
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    
    except Exception as e:
        # Handle unexpected errors during file upload
        if temp_file:
            temp_file.close()
            if temp_file.name:
                Path(temp_file.name).unlink(missing_ok=True)
        
        log_with_context(
            logger,
            "error",
            "Unexpected error during file upload",
            error=e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to process audio file upload",
                    "details": str(e)
                }
            }
        )


@app.get(
    "/api/v1/transcribe/batch/{job_id}",
    response_model=BatchStatusResponse,
    tags=["Transcription"],
    summary="Get batch transcription job status and result",
    responses={
        200: {
            "description": "Job status retrieved successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "pending": {
                            "summary": "Job pending",
                            "value": {
                                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                                "status": "pending",
                                "transcription": None,
                                "error": None
                            }
                        },
                        "processing": {
                            "summary": "Job processing",
                            "value": {
                                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                                "status": "processing",
                                "transcription": None,
                                "error": None
                            }
                        },
                        "completed": {
                            "summary": "Job completed",
                            "value": {
                                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                                "status": "completed",
                                "transcription": "سلام، این یک نمونه متن فارسی است که از صدا به متن تبدیل شده است.",
                                "error": None
                            }
                        },
                        "failed": {
                            "summary": "Job failed",
                            "value": {
                                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                                "status": "failed",
                                "transcription": None,
                                "error": "Audio file is corrupted or unreadable"
                            }
                        }
                    }
                }
            }
        },
        404: {
            "description": "Job not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "JOB_NOT_FOUND",
                            "message": "Job with ID 550e8400-e29b-41d4-a716-446655440000 not found",
                            "details": None
                        }
                    }
                }
            }
        },
        503: {
            "description": "Service not available",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "SERVICE_UNAVAILABLE",
                            "message": "Transcription service is not available",
                            "details": None
                        }
                    }
                }
            }
        }
    }
)
async def get_batch_transcription_status(job_id: str) -> BatchStatusResponse:
    """
    Get the status and result of a batch transcription job.
    
    Query this endpoint with the job_id returned from the POST endpoint
    to check the transcription progress and retrieve the result when complete.
    
    **Job Status Values:**
    - `pending`: Job is queued and waiting to be processed
    - `processing`: Job is currently being transcribed
    - `completed`: Transcription finished successfully (transcription field contains result)
    - `failed`: Transcription failed (error field contains error message)
    
    **Polling Strategy:**
    - Poll this endpoint periodically to check job status
    - Recommended polling interval: 1-2 seconds for short clips, 5-10 seconds for long files
    - Stop polling when status is "completed" or "failed"
    
    **Response Fields:**
    - `job_id`: The unique identifier of the job
    - `status`: Current job status (pending/processing/completed/failed)
    - `transcription`: Persian text transcription (only present when status is "completed")
    - `error`: Error message (only present when status is "failed")
    
    **Transcription Output:**
    - Plain text format without timestamps or metadata
    - Persian script (not Latin transliteration)
    - Natural sentence structure and spacing preserved
    
    Args:
        job_id: The unique identifier of the transcription job
    
    Returns:
        BatchStatusResponse: Job status and transcription result (if completed)
    
    Raises:
        HTTPException 404: Job ID not found
        HTTPException 503: Service not available
    
    Example (curl):
        ```bash
        curl http://localhost:8000/api/v1/transcribe/batch/550e8400-e29b-41d4-a716-446655440000
        ```
        
        Response (completed):
        ```json
        {
            "job_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "completed",
            "transcription": "سلام، این یک نمونه متن فارسی است.",
            "error": null
        }
        ```
    
    Example (Python):
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
    """
    # Check if service is available
    if not transcription_service:
        logger.error("Transcription service not available")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "Transcription service is not available",
                    "details": None
                }
            }
        )
    
    # Get job status
    job = transcription_service.get_batch_status(job_id)
    
    if not job:
        log_with_context(
            logger,
            "warning",
            "Job not found",
            job_id=job_id
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "JOB_NOT_FOUND",
                    "message": f"Job with ID {job_id} not found",
                    "details": None
                }
            }
        )
    
    # Return job status
    return BatchStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        transcription=job.transcription,
        error=job.error_message
    )


# WebSocket streaming endpoint

@app.websocket("/api/v1/transcribe/stream")
async def websocket_streaming_transcription(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time streaming transcription.
    
    This endpoint establishes a bidirectional WebSocket connection for
    streaming audio data and receiving transcription results in real-time.
    
    **Connection Protocol:**
    1. Client connects to the WebSocket endpoint
    2. Server accepts connection and initializes transcription
    3. Client sends audio chunks as binary data
    4. Server processes chunks incrementally
    5. Server sends partial transcription results as JSON messages
    6. Client closes connection when done
    7. Server sends final transcription before closing
    
    **Audio Format:**
    - Send raw audio data as binary WebSocket messages
    - Recommended chunk size: 4096-8192 bytes
    - Supported formats: WAV, MP3, OGG, M4A (same as batch endpoint)
    - Audio is buffered and processed in segments for better accuracy
    
    **Message Format (Server to Client):**
    ```json
    {
        "type": "partial" | "final" | "error",
        "text": "transcribed text in Persian",
        "timestamp": 1234567890.123
    }
    ```
    
    **Message Types:**
    - `partial`: Intermediate transcription result (may change as more audio is received)
    - `final`: Final transcription result (sent when connection closes)
    - `error`: Error message (sent when processing fails)
    
    **Error Handling:**
    - If an error occurs, server sends error message with type "error"
    - Connection is maintained where possible for stability
    - Client should handle errors gracefully and can retry
    
    **Buffer Management:**
    - Server maintains an internal buffer for audio chunks
    - Maximum buffer size is configurable (default: 10 MB)
    - If buffer exceeds limit, server sends error message
    
    **Performance Considerations:**
    - Streaming transcription has higher latency than batch processing
    - Partial results may change as more context is received
    - For best accuracy, send audio in consistent chunk sizes
    - Close connection properly to receive final transcription
    
    Requirements:
    - 3.1: Establish bidirectional communication channel
    - 3.2: Process audio data incrementally
    - 3.3: Return partial transcription segments
    - 3.4: Finalize transcription on connection close
    - 3.5: Handle errors and maintain connection stability
    - 5.2: WebSocket endpoint for streaming
    
    Example Usage (Python with websockets library):
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
    
    Example Usage (JavaScript):
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
    
    Example Usage (curl with websocat):
        ```bash
        # Install websocat: https://github.com/vi/websocat
        cat audio.wav | websocat ws://localhost:8000/api/v1/transcribe/stream
        ```
    """
    # Accept the WebSocket connection
    await websocket.accept()
    logger.info("WebSocket connection established")
    
    # Check if service is available
    if not transcription_service:
        error_msg = StreamTranscriptionMessage(
            type="error",
            text="Transcription service is not available",
            timestamp=time.time()
        )
        await websocket.send_text(error_msg.model_dump_json())
        await websocket.close(code=1011, reason="Service unavailable")
        logger.error("WebSocket connection rejected: service not available")
        return
    
    # Initialize model on first request if not already done
    if not transcription_service.is_ready():
        try:
            logger.info("Initializing transcription model for WebSocket connection...")
            transcription_service.initialize()
        except Exception as e:
            error_msg = StreamTranscriptionMessage(
                type="error",
                text=f"Transcription service is initializing. Please retry in a few moments: {str(e)}",
                timestamp=time.time()
            )
            await websocket.send_text(error_msg.model_dump_json())
            await websocket.close(code=1011, reason="Service initializing")
            logger.error(f"WebSocket connection rejected: initialization failed - {e}")
            return
    
    # Clear any previous streaming buffer
    transcription_service.clear_stream_buffer()
    
    try:
        # Process incoming audio chunks
        while True:
            try:
                # Receive audio chunk (binary data)
                audio_chunk = await websocket.receive_bytes()
                
                if not audio_chunk:
                    logger.debug("Received empty audio chunk, skipping")
                    continue
                
                logger.debug(f"Received audio chunk: {len(audio_chunk)} bytes")
                
                # Process the chunk and get partial transcription
                try:
                    partial_result = await transcription_service.transcribe_stream_chunk(
                        audio_chunk=audio_chunk
                    )
                    
                    # Send partial result if available
                    if partial_result:
                        message = StreamTranscriptionMessage(
                            type="partial",
                            text=partial_result,
                            timestamp=time.time()
                        )
                        await websocket.send_text(message.model_dump_json())
                        logger.info(f"Sent partial transcription: {len(partial_result)} chars")
                
                except ValueError as e:
                    # Buffer size exceeded or other validation error
                    error_msg = StreamTranscriptionMessage(
                        type="error",
                        text=f"Audio processing error: {str(e)}",
                        timestamp=time.time()
                    )
                    await websocket.send_text(error_msg.model_dump_json())
                    logger.warning(f"Audio processing error: {e}")
                    # Continue processing, don't close connection
                
                except Exception as e:
                    # Unexpected error during chunk processing
                    error_msg = StreamTranscriptionMessage(
                        type="error",
                        text=f"Transcription error: {str(e)}",
                        timestamp=time.time()
                    )
                    await websocket.send_text(error_msg.model_dump_json())
                    logger.error(f"Transcription error: {e}", exc_info=True)
                    # Continue processing, maintain connection stability
            
            except WebSocketDisconnect:
                # Client disconnected
                logger.info("WebSocket client disconnected")
                break
            
            except Exception as e:
                # Unexpected error receiving data
                logger.error(f"Error receiving WebSocket data: {e}", exc_info=True)
                break
        
        # Connection closed - finalize transcription
        logger.info("Finalizing streaming transcription")
        
        try:
            final_result = await transcription_service.finalize_stream()
            
            if final_result:
                # Send final transcription
                final_message = StreamTranscriptionMessage(
                    type="final",
                    text=final_result,
                    timestamp=time.time()
                )
                await websocket.send_text(final_message.model_dump_json())
                logger.info(f"Sent final transcription: {len(final_result)} chars")
            else:
                # Send empty final message to indicate completion
                final_message = StreamTranscriptionMessage(
                    type="final",
                    text="",
                    timestamp=time.time()
                )
                await websocket.send_text(final_message.model_dump_json())
                logger.info("Sent empty final transcription (no remaining content)")
        
        except Exception as e:
            # Error during finalization
            error_msg = StreamTranscriptionMessage(
                type="error",
                text=f"Finalization error: {str(e)}",
                timestamp=time.time()
            )
            await websocket.send_text(error_msg.model_dump_json())
            logger.error(f"Finalization error: {e}", exc_info=True)
    
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"Unexpected WebSocket error: {e}", exc_info=True)
        try:
            error_msg = StreamTranscriptionMessage(
                type="error",
                text=f"Unexpected error: {str(e)}",
                timestamp=time.time()
            )
            await websocket.send_text(error_msg.model_dump_json())
        except Exception:
            # If we can't even send the error message, just log it
            logger.error("Failed to send error message to client")
    
    finally:
        # Clean up and close connection
        try:
            transcription_service.clear_stream_buffer()
            await websocket.close()
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.warning(f"Error closing WebSocket: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
