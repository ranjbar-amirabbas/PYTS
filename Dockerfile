# Persian Transcription API - Multi-stage Docker Build
# This Dockerfile creates a minimal production image with all dependencies

# =============================================================================
# Base Stage: System Dependencies
# =============================================================================
FROM python:3.11-slim as base

# Install system dependencies including FFmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# =============================================================================
# Builder Stage: Python Dependencies and Model Download
# =============================================================================
FROM base as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python packages in a virtual environment for easy copying
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Download Whisper model weights at build time
# This ensures the model is baked into the image for offline operation
# Default to medium model, can be overridden with build arg
ARG WHISPER_MODEL_SIZE=medium
ENV WHISPER_MODEL_SIZE=${WHISPER_MODEL_SIZE}

# Pre-download the Whisper model by running a simple import
# This caches the model in ~/.cache/whisper
RUN python -c "import whisper; whisper.load_model('${WHISPER_MODEL_SIZE}')"

# =============================================================================
# Final Stage: Minimal Production Image
# =============================================================================
FROM base as final

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy Whisper model cache from builder
COPY --from=builder /root/.cache/whisper /root/.cache/whisper

# Set PATH to use virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY app/ /app/app/

# Create directories for temporary files and logs
RUN mkdir -p /app/temp /app/logs /app/models

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Default configuration (can be overridden at runtime)
ENV WHISPER_MODEL_SIZE=medium
ENV MAX_CONCURRENT_WORKERS=4
ENV MAX_QUEUE_SIZE=100
ENV MAX_FILE_SIZE_MB=500
ENV API_PORT=8000
ENV API_HOST=0.0.0.0
ENV LOG_LEVEL=INFO
ENV JOB_CLEANUP_MAX_AGE_HOURS=24

# Expose API port
EXPOSE 8000

# Health check command
# Checks if the API is responding and the model is loaded
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; import json; \
    response = urllib.request.urlopen('http://localhost:8000/api/v1/health'); \
    data = json.loads(response.read()); \
    exit(0 if data.get('status') == 'healthy' and data.get('model_loaded') else 1)"

# Run the application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
