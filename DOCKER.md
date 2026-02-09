# Docker Deployment Guide

This guide provides detailed instructions for deploying the Persian Transcription API using Docker.

## Table of Contents

- [Quick Start](#quick-start)
- [Building the Image](#building-the-image)
- [Running the Container](#running-the-container)
- [Configuration](#configuration)
- [Health Checks](#health-checks)
- [Troubleshooting](#troubleshooting)
- [Production Deployment](#production-deployment)

## Quick Start

The fastest way to get started is using Docker Compose:

```bash
# Start the service
docker-compose up -d

# Check health
curl http://localhost:8000/api/v1/health

# View logs
docker-compose logs -f

# Stop the service
docker-compose down
```

## Building the Image

### Multi-Stage Build

The Dockerfile uses a multi-stage build process to create a minimal production image:

1. **Base Stage**: Installs system dependencies (FFmpeg, Python)
2. **Builder Stage**: Installs Python packages and downloads Whisper model
3. **Final Stage**: Copies only necessary files for minimal image size

### Build Commands

Build with default settings (medium model):
```bash
docker build -t persian-transcription-api:latest .
```

Build with a specific Whisper model size:
```bash
# Small model (faster, less accurate)
docker build --build-arg WHISPER_MODEL_SIZE=small -t persian-transcription-api:small .

# Large model (slower, more accurate)
docker build --build-arg WHISPER_MODEL_SIZE=large -t persian-transcription-api:large .
```

Build with BuildKit for faster builds:
```bash
DOCKER_BUILDKIT=1 docker build -t persian-transcription-api:latest .
```

### Build Time

Build times vary based on model size and network speed:

- **tiny/base**: ~5 minutes
- **small**: ~10 minutes
- **medium**: ~15 minutes
- **large**: ~20 minutes

The Whisper model is downloaded during the build process, so the first build will take longer.

## Running the Container

### Using Docker Compose (Recommended)

Create a `.env` file from the example:
```bash
cp .env.example .env
```

Edit `.env` to customize configuration, then start:
```bash
docker-compose up -d
```

### Using Docker Run

Basic run:
```bash
docker run -d \
  --name persian-transcription-api \
  -p 8000:8000 \
  persian-transcription-api:latest
```

With volume mounts for persistence:
```bash
docker run -d \
  --name persian-transcription-api \
  -p 8000:8000 \
  -v $(pwd)/temp:/app/temp \
  -v $(pwd)/logs:/app/logs \
  -v whisper-models:/root/.cache/whisper \
  persian-transcription-api:latest
```

With custom configuration:
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

## Configuration

### Environment Variables

All configuration is done through environment variables:

#### Whisper Model Configuration

- `WHISPER_MODEL_SIZE`: Model size (default: `medium`)
  - `tiny`: Fastest, lowest accuracy (~1GB RAM)
  - `base`: Fast, low accuracy (~1GB RAM)
  - `small`: Balanced (~2GB RAM)
  - `medium`: Good accuracy, moderate speed (~5GB RAM) **[RECOMMENDED]**
  - `large`: Best accuracy, slower (~10GB RAM)

#### Concurrency Configuration

- `MAX_CONCURRENT_WORKERS`: Maximum concurrent transcription workers (default: `4`)
- `MAX_QUEUE_SIZE`: Maximum queued jobs (default: `100`)

#### File Upload Configuration

- `MAX_FILE_SIZE_MB`: Maximum audio file size in MB (default: `500`)

#### API Configuration

- `API_PORT`: API port inside container (default: `8000`)
- `API_HOST`: API host (default: `0.0.0.0`)

#### Logging Configuration

- `LOG_LEVEL`: Logging level (default: `INFO`)
  - Options: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

#### Job Management Configuration

- `JOB_CLEANUP_MAX_AGE_HOURS`: Hours before completed jobs are cleaned up (default: `24`)

#### Streaming Configuration

- `STREAM_MIN_CHUNK_SIZE`: Minimum chunk size for streaming (default: `102400` bytes / 100 KB)
- `STREAM_MAX_BUFFER_SIZE`: Maximum buffer size for streaming (default: `10485760` bytes / 10 MB)

### Volume Mounts

The container uses the following directories:

- `/root/.cache/whisper`: Whisper model cache (mount to persist models)
- `/app/temp`: Temporary audio processing files
- `/app/logs`: Application logs

Example volume configuration:
```yaml
volumes:
  - whisper-models:/root/.cache/whisper  # Persist model cache
  - ./temp:/app/temp                      # Temporary files
  - ./logs:/app/logs                      # Application logs
```

## Health Checks

The container includes automatic health checks that run every 30 seconds.

### Health Check Command

```bash
python -c "import urllib.request; import json; \
response = urllib.request.urlopen('http://localhost:8000/api/v1/health'); \
data = json.loads(response.read()); \
exit(0 if data.get('status') == 'healthy' and data.get('model_loaded') else 1)"
```

### Health Check Configuration

- **Interval**: 30 seconds
- **Timeout**: 10 seconds
- **Start Period**: 60 seconds (grace period for model loading)
- **Retries**: 3

### Checking Health Manually

```bash
# Using curl
curl http://localhost:8000/api/v1/health

# Using Docker
docker inspect --format='{{.State.Health.Status}}' persian-transcription-api

# Using Docker Compose
docker-compose ps
```

Expected healthy response:
```json
{
  "status": "healthy",
  "model_loaded": true,
  "model_size": "medium"
}
```

## Troubleshooting

### Container Won't Start

1. Check logs:
   ```bash
   docker logs persian-transcription-api
   ```

2. Verify port is not in use:
   ```bash
   lsof -i :8000  # On macOS/Linux
   netstat -ano | findstr :8000  # On Windows
   ```

3. Check resource availability:
   ```bash
   docker stats persian-transcription-api
   ```

### Model Not Loading

If the health check shows `model_loaded: false`:

1. Check if model was downloaded during build:
   ```bash
   docker exec persian-transcription-api ls -lh /root/.cache/whisper/
   ```

2. Check available memory:
   ```bash
   docker stats persian-transcription-api
   ```

3. Try a smaller model size:
   ```bash
   docker run -e WHISPER_MODEL_SIZE=small ...
   ```

### Out of Memory

If the container crashes with OOM errors:

1. Increase Docker memory limit:
   - Docker Desktop: Settings → Resources → Memory
   - docker-compose.yml: Adjust `deploy.resources.limits.memory`

2. Use a smaller model:
   ```bash
   docker run -e WHISPER_MODEL_SIZE=small ...
   ```

3. Reduce concurrent workers:
   ```bash
   docker run -e MAX_CONCURRENT_WORKERS=2 ...
   ```

### Slow Transcription

If transcription is slow:

1. Check CPU usage:
   ```bash
   docker stats persian-transcription-api
   ```

2. Use a smaller model for faster processing:
   ```bash
   docker run -e WHISPER_MODEL_SIZE=small ...
   ```

3. Increase concurrent workers (if you have CPU/memory):
   ```bash
   docker run -e MAX_CONCURRENT_WORKERS=8 ...
   ```

### Permission Errors

If you get permission errors with volume mounts:

```bash
# Create directories with correct permissions
mkdir -p temp logs
chmod 777 temp logs

# Or run container with specific user
docker run --user $(id -u):$(id -g) ...
```

## Production Deployment

### Resource Recommendations

Based on Whisper model size:

| Model | RAM | CPU Cores | Concurrent Workers |
|-------|-----|-----------|-------------------|
| tiny | 2 GB | 2 | 4 |
| base | 2 GB | 2 | 4 |
| small | 4 GB | 4 | 4 |
| medium | 8 GB | 8 | 4 |
| large | 16 GB | 16 | 2 |

### Production Configuration

Example production docker-compose.yml:

```yaml
services:
  persian-transcription-api:
    image: persian-transcription-api:latest
    restart: always
    ports:
      - "8000:8000"
    environment:
      WHISPER_MODEL_SIZE: medium
      MAX_CONCURRENT_WORKERS: 4
      LOG_LEVEL: INFO
    volumes:
      - whisper-models:/root/.cache/whisper
      - ./temp:/app/temp
      - ./logs:/app/logs
    deploy:
      resources:
        limits:
          memory: 8G
          cpus: '8'
        reservations:
          memory: 4G
          cpus: '4'
    healthcheck:
      interval: 30s
      timeout: 10s
      start_period: 60s
      retries: 3

volumes:
  whisper-models:
```

### Security Considerations

1. **Run as non-root user** (optional):
   ```dockerfile
   # Add to Dockerfile
   RUN useradd -m -u 1000 appuser
   USER appuser
   ```

2. **Limit container capabilities**:
   ```yaml
   security_opt:
     - no-new-privileges:true
   cap_drop:
     - ALL
   ```

3. **Use read-only root filesystem** (if possible):
   ```yaml
   read_only: true
   tmpfs:
     - /tmp
     - /app/temp
   ```

4. **Network isolation**:
   ```yaml
   networks:
     - transcription-network
   ```

### Monitoring

1. **Health checks**: Use the built-in health endpoint
2. **Logs**: Mount logs volume and use log aggregation
3. **Metrics**: Consider adding Prometheus metrics endpoint
4. **Alerts**: Set up alerts for health check failures

### Backup and Recovery

1. **Model cache**: The Whisper model is baked into the image, no backup needed
2. **Logs**: Regularly backup the logs volume
3. **Temporary files**: No backup needed, these are transient

### Scaling

For horizontal scaling:

1. Use a load balancer (nginx, HAProxy, etc.)
2. Run multiple container instances
3. Share volume mounts or use object storage for temporary files
4. Consider using Kubernetes for orchestration

Example with multiple instances:
```bash
docker-compose up --scale persian-transcription-api=3
```

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Whisper Documentation](https://github.com/openai/whisper)
- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
