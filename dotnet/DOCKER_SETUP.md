# Docker Setup Guide for ASP.NET Core Transcription API

This guide explains how to build and run the Transcription API using Docker.

## Prerequisites

- Docker Engine 20.10+ or Docker Desktop
- Docker Compose 2.0+
- At least 4GB of free disk space (for model files)
- At least 2GB of RAM allocated to Docker

## Quick Start

### 1. Build and Run with Docker Compose

```bash
# Navigate to the dotnet directory
cd dotnet

# Build and start the service
docker-compose up -d

# View logs
docker-compose logs -f transcription-api

# Stop the service
docker-compose down
```

### 2. Build Docker Image Manually

```bash
# Navigate to the TranscriptionApi directory
cd dotnet/TranscriptionApi

# Build the image (default: medium model)
docker build -t transcription-api:latest .

# Build with a different model size
docker build --build-arg WHISPER_MODEL_SIZE=small -t transcription-api:small .

# Run the container
docker run -d \
  --name transcription-api \
  -p 5226:5226 \
  -v ~/.cache/whisper:/root/.cache/whisper \
  transcription-api:latest
```

## Configuration

### Environment Variables

Configure the API using environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ASPNETCORE_ENVIRONMENT` | `Production` | ASP.NET Core environment |
| `Transcription__WhisperModelSize` | `medium` | Whisper model size (tiny, base, small, medium, large) |
| `Transcription__MaxConcurrentWorkers` | `4` | Maximum concurrent transcription jobs |
| `Transcription__MaxQueueSize` | `100` | Maximum job queue size |
| `Transcription__MaxFileSizeMB` | `500` | Maximum audio file size in MB |
| `Transcription__JobCleanupMaxAgeHours` | `24` | Hours before cleaning up old jobs |

### Model Sizes

Choose the appropriate model size based on your needs:

| Model | Size | Speed | Accuracy | Use Case |
|-------|------|-------|----------|----------|
| `tiny` | ~75MB | Fastest | Lower | Quick testing, real-time |
| `base` | ~142MB | Fast | Good | Development, demos |
| `small` | ~466MB | Medium | Better | Production (balanced) |
| `medium` | ~1.5GB | Slow | High | Production (accurate) |
| `large` | ~2.9GB | Slowest | Highest | Maximum accuracy needed |

### Docker Compose Configuration

Edit `docker-compose.yml` to customize:

```yaml
services:
  transcription-api:
    build:
      args:
        WHISPER_MODEL_SIZE: small  # Change model size
    environment:
      - Transcription__MaxConcurrentWorkers=2  # Adjust workers
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
```

## Usage Examples

### 1. Check API Health

```bash
curl http://localhost:5226/api/health
```

### 2. Transcribe Audio File

```bash
curl -X POST http://localhost:5226/api/transcription \
  -F "file=@audio.wav" \
  -F "language=en"
```

### 3. Check Job Status

```bash
curl http://localhost:5226/api/transcription/{jobId}
```

### 4. View Swagger Documentation

Open in browser: http://localhost:5226

## Volume Management

### Persistent Volumes

The setup uses Docker volumes for:

- **transcription-temp**: Temporary audio files during processing
- **transcription-logs**: Application logs
- **Model cache**: Whisper model files (mounted from host)

### Managing Volumes

```bash
# List volumes
docker volume ls

# Inspect volume
docker volume inspect transcription-temp

# Remove volumes (when stopped)
docker-compose down -v

# Backup logs
docker cp transcription-api:/app/logs ./backup-logs
```

## Performance Optimization

### 1. Resource Limits

Add resource limits in `docker-compose.yml`:

```yaml
services:
  transcription-api:
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 8G
```

### 2. Use Smaller Model

For faster processing with less accuracy:

```bash
docker build --build-arg WHISPER_MODEL_SIZE=small -t transcription-api:small .
```

### 3. Adjust Worker Count

Reduce workers for limited resources:

```yaml
environment:
  - Transcription__MaxConcurrentWorkers=2
```

## Troubleshooting

### Model Download Issues

If the model fails to download during build:

```bash
# Pre-download model manually
mkdir -p ~/.cache/whisper
cd ~/.cache/whisper
wget https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin

# Rebuild with cached model
docker-compose build --no-cache
```

### Memory Issues

If you see out-of-memory errors:

1. Increase Docker memory limit (Docker Desktop → Settings → Resources)
2. Use a smaller model size
3. Reduce `MaxConcurrentWorkers`

### Port Already in Use

If port 5226 is already in use:

```yaml
# Change port in docker-compose.yml
ports:
  - "5227:5226"  # Map to different host port
```

### View Container Logs

```bash
# Follow logs
docker-compose logs -f transcription-api

# Last 100 lines
docker-compose logs --tail=100 transcription-api

# Logs since 1 hour ago
docker-compose logs --since 1h transcription-api
```

### Access Container Shell

```bash
# Execute bash in running container
docker-compose exec transcription-api bash

# Check model files
docker-compose exec transcription-api ls -lh /root/.cache/whisper
```

## Production Deployment

### 1. Build Optimized Image

```bash
# Build with production optimizations
docker build \
  --build-arg WHISPER_MODEL_SIZE=medium \
  -t transcription-api:1.0.0 \
  -t transcription-api:latest \
  .
```

### 2. Use Docker Secrets

For sensitive configuration:

```yaml
services:
  transcription-api:
    secrets:
      - api_key
    environment:
      - API_KEY_FILE=/run/secrets/api_key

secrets:
  api_key:
    file: ./secrets/api_key.txt
```

### 3. Enable HTTPS

Mount SSL certificates:

```yaml
volumes:
  - ./certs:/app/certs:ro
environment:
  - ASPNETCORE_URLS=https://+:5226
  - ASPNETCORE_Kestrel__Certificates__Default__Path=/app/certs/cert.pfx
  - ASPNETCORE_Kestrel__Certificates__Default__Password=${CERT_PASSWORD}
```

### 4. Health Monitoring

Use Docker health checks with orchestration:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:5226/api/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s
```

## Multi-Stage Build Details

The Dockerfile uses a multi-stage build:

1. **Base**: Runtime dependencies (FFmpeg)
2. **Build**: Compile .NET application
3. **Publish**: Create optimized output
4. **Model-download**: Pre-download Whisper model
5. **Final**: Minimal production image

This approach:
- Reduces final image size
- Includes model in image (no runtime download)
- Separates build and runtime dependencies
- Enables layer caching for faster rebuilds

## Cleanup

```bash
# Stop and remove containers
docker-compose down

# Remove containers and volumes
docker-compose down -v

# Remove images
docker rmi transcription-api:latest

# Clean up everything
docker system prune -a --volumes
```

## Next Steps

- Configure reverse proxy (nginx, Traefik)
- Set up monitoring (Prometheus, Grafana)
- Implement log aggregation (ELK, Loki)
- Add CI/CD pipeline
- Deploy to Kubernetes or cloud platform
