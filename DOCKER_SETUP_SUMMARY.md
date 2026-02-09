# Docker Setup Summary

This document summarizes the Docker configuration created for the Persian Transcription API.

## Files Created

### 1. Dockerfile
**Location**: `./Dockerfile`

A multi-stage Docker build configuration that:
- **Base Stage**: Installs Python 3.11 and FFmpeg
- **Builder Stage**: Installs Python dependencies and downloads Whisper model
- **Final Stage**: Creates minimal production image (~2-5GB depending on model)

Key features:
- Multi-stage build for minimal image size
- Pre-downloads Whisper model during build (offline operation)
- Configurable model size via build argument
- Health check endpoint integration
- Proper environment variable configuration

### 2. docker-compose.yml
**Location**: `./docker-compose.yml`

Docker Compose configuration for easy deployment:
- Service definition with port mapping
- Volume mounts for models, temp files, and logs
- Environment variable configuration
- Resource limits and health checks
- Named volume for model persistence

### 3. .dockerignore
**Location**: `./.dockerignore`

Excludes unnecessary files from Docker build context:
- Python cache files and virtual environments
- Test files and coverage reports
- IDE configuration files
- Git files and documentation
- Kiro specs and development files

### 4. .env.example
**Location**: `./.env.example`

Example environment configuration file with:
- Detailed documentation for all configuration options
- Sensible default values
- Resource recommendations based on model size
- Comments explaining each setting

### 5. DOCKER.md
**Location**: `./DOCKER.md`

Comprehensive Docker deployment guide covering:
- Quick start instructions
- Building and running the container
- Configuration options
- Health checks
- Troubleshooting common issues
- Production deployment recommendations
- Security considerations
- Scaling strategies

### 6. README.md (Updated)
**Location**: `./README.md`

Added Docker deployment section with:
- Quick start with Docker Compose
- Manual build and run instructions
- Configuration table
- Resource requirements by model size
- Health check information

## Task Requirements Met

### Task 11.1: Create Dockerfile with multi-stage build
✅ **Base stage**: Install system dependencies (FFmpeg, Python)
✅ **Builder stage**: Install Python packages and download Whisper model
✅ **Final stage**: Copy only necessary files for minimal image size
✅ **Configure health check command**
✅ **Requirements**: 6.1, 6.2, 6.3, 6.6

## Quick Start

### Using Docker Compose (Recommended)
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

### Using Docker Build and Run
```bash
# Build the image
docker build -t persian-transcription-api:latest .

# Run the container
docker run -d \
  --name persian-transcription-api \
  -p 8000:8000 \
  -v $(pwd)/temp:/app/temp \
  -v $(pwd)/logs:/app/logs \
  persian-transcription-api:latest

# Check health
curl http://localhost:8000/api/v1/health
```

## Configuration Options

All configuration is done through environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `WHISPER_MODEL_SIZE` | `medium` | Model size (tiny, base, small, medium, large) |
| `MAX_CONCURRENT_WORKERS` | `4` | Maximum concurrent transcription workers |
| `MAX_QUEUE_SIZE` | `100` | Maximum queued jobs |
| `MAX_FILE_SIZE_MB` | `500` | Maximum audio file size in MB |
| `API_PORT` | `8000` | API port (container internal) |
| `LOG_LEVEL` | `INFO` | Logging level |
| `JOB_CLEANUP_MAX_AGE_HOURS` | `24` | Hours before job cleanup |

See `.env.example` for complete list.

## Resource Requirements

| Model Size | RAM Required | CPU Cores | Build Time | Image Size |
|------------|--------------|-----------|------------|------------|
| tiny | 1 GB | 1-2 | ~5 min | ~2 GB |
| base | 1 GB | 1-2 | ~5 min | ~2 GB |
| small | 2 GB | 2-4 | ~10 min | ~3 GB |
| medium | 5 GB | 4-8 | ~15 min | ~4 GB |
| large | 10 GB | 8+ | ~20 min | ~6 GB |

**Recommended**: Use `medium` model for production (best balance of accuracy and performance).

## Health Checks

The container includes automatic health checks:
- **Interval**: 30 seconds
- **Timeout**: 10 seconds
- **Start Period**: 60 seconds (grace period for model loading)
- **Retries**: 3

Health check verifies:
1. API is responding
2. Whisper model is loaded and ready

## Volume Mounts

The container uses these directories:
- `/root/.cache/whisper`: Whisper model cache (persist with named volume)
- `/app/temp`: Temporary audio processing files
- `/app/logs`: Application logs

## Offline Operation

The Whisper model is downloaded during the Docker build process and baked into the image. This ensures:
- ✅ No internet connectivity required at runtime
- ✅ Faster container startup (model already cached)
- ✅ Consistent model version across deployments
- ✅ Meets Requirement 7.1, 7.2, 7.3, 7.4 (offline operation)

## Next Steps

1. **Test the build**: Run `docker build -t persian-transcription-api:latest .`
2. **Test the container**: Run `docker-compose up -d`
3. **Verify health**: Run `curl http://localhost:8000/api/v1/health`
4. **Test transcription**: Upload an audio file to the API
5. **Review logs**: Check `docker-compose logs -f` for any issues

## Troubleshooting

If you encounter issues:
1. Check logs: `docker-compose logs -f`
2. Verify health: `curl http://localhost:8000/api/v1/health`
3. Check resources: `docker stats persian-transcription-api`
4. See DOCKER.md for detailed troubleshooting guide

## Additional Documentation

- **DOCKER.md**: Comprehensive Docker deployment guide
- **README.md**: Project overview and quick start
- **.env.example**: Configuration options with detailed comments
- **requirements.txt**: Python dependencies
