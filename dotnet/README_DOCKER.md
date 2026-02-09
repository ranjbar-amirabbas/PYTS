# Docker Setup for ASP.NET Core Transcription API

Complete guide for running the Transcription API with Docker, including Whisper.net integration.

## 🚀 Quick Start

### Option 1: Using Docker Compose (Recommended)

```bash
cd dotnet

# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Test the API
curl http://localhost:5226/api/health

# Stop
docker-compose down
```

### Option 2: Using the Build Script

```bash
cd dotnet

# Make script executable (first time only)
chmod +x build-and-run.sh

# Build and start with medium model
./build-and-run.sh medium up

# View logs
./build-and-run.sh medium logs

# Stop
./build-and-run.sh medium down
```

### Option 3: Manual Docker Commands

```bash
cd dotnet/TranscriptionApi

# Build
docker build -t transcription-api:latest .

# Run
docker run -d \
  --name transcription-api \
  -p 5226:5226 \
  -v ~/.cache/whisper:/root/.cache/whisper \
  transcription-api:latest

# View logs
docker logs -f transcription-api

# Stop
docker stop transcription-api
docker rm transcription-api
```

## 📋 Prerequisites

- **Docker**: Version 20.10 or higher
- **Docker Compose**: Version 2.0 or higher
- **Disk Space**: At least 4GB free (for model files)
- **RAM**: At least 2GB allocated to Docker (4GB+ recommended)

### Install Docker

**macOS:**
```bash
brew install --cask docker
```

**Linux:**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

**Windows:**
Download from [Docker Desktop](https://www.docker.com/products/docker-desktop)

## 🔧 Configuration

### Model Sizes

Choose based on your accuracy vs. speed requirements:

| Model | Size | RAM | Speed | Accuracy | Best For |
|-------|------|-----|-------|----------|----------|
| `tiny` | 75MB | 1GB | ⚡⚡⚡⚡⚡ | ⭐⭐ | Testing, demos |
| `base` | 142MB | 1GB | ⚡⚡⚡⚡ | ⭐⭐⭐ | Development |
| `small` | 466MB | 2GB | ⚡⚡⚡ | ⭐⭐⭐⭐ | Production (balanced) |
| `medium` | 1.5GB | 4GB | ⚡⚡ | ⭐⭐⭐⭐⭐ | Production (accurate) |
| `large` | 2.9GB | 8GB | ⚡ | ⭐⭐⭐⭐⭐ | Maximum accuracy |

### Build with Different Model

```bash
# Build with small model
docker build --build-arg WHISPER_MODEL_SIZE=small -t transcription-api:small .

# Or with docker-compose
WHISPER_MODEL_SIZE=small docker-compose build
```

### Environment Variables

Edit `docker-compose.yml` or pass via `-e`:

```yaml
environment:
  - ASPNETCORE_ENVIRONMENT=Production
  - Transcription__WhisperModelSize=medium
  - Transcription__MaxConcurrentWorkers=4
  - Transcription__MaxQueueSize=100
  - Transcription__MaxFileSizeMB=500
  - Transcription__JobCleanupMaxAgeHours=24
```

## 📊 Usage Examples

### 1. Health Check

```bash
curl http://localhost:5226/api/health
```

Expected response:
```json
{
  "status": "Healthy",
  "modelLoaded": true,
  "modelSize": "medium",
  "timestamp": "2024-02-09T12:00:00Z"
}
```

### 2. Transcribe Audio File

```bash
# Transcribe with auto language detection
curl -X POST http://localhost:5226/api/transcription \
  -F "file=@audio.wav"

# Transcribe with specific language
curl -X POST http://localhost:5226/api/transcription \
  -F "file=@audio.mp3" \
  -F "language=en"
```

### 3. Check Job Status

```bash
curl http://localhost:5226/api/transcription/{jobId}
```

### 4. Access Swagger UI

Open in browser: http://localhost:5226

## 🐛 Troubleshooting

### Issue: Port Already in Use

```bash
# Check what's using the port
lsof -i :5226

# Kill the process
kill -9 <PID>

# Or change the port in docker-compose.yml
ports:
  - "5227:5226"
```

### Issue: Model Download Fails

Pre-download the model manually:

```bash
mkdir -p ~/.cache/whisper
cd ~/.cache/whisper

# Download medium model
wget https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin

# Rebuild
docker-compose build --no-cache
```

### Issue: Out of Memory

1. **Increase Docker memory limit:**
   - Docker Desktop → Settings → Resources → Memory
   - Set to at least 4GB (8GB recommended)

2. **Use smaller model:**
   ```bash
   WHISPER_MODEL_SIZE=small docker-compose up -d
   ```

3. **Reduce concurrent workers:**
   ```yaml
   environment:
     - Transcription__MaxConcurrentWorkers=2
   ```

### Issue: Container Won't Start

```bash
# Check logs
docker-compose logs transcription-api

# Check container status
docker ps -a

# Restart container
docker-compose restart

# Rebuild from scratch
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Issue: Slow Performance

1. **Check resource usage:**
   ```bash
   docker stats transcription-api
   ```

2. **Optimize settings:**
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '4.0'
         memory: 8G
   ```

3. **Use GPU acceleration** (if available):
   - Install NVIDIA Container Toolkit
   - Add GPU support to docker-compose.yml

## 📁 Volume Management

### View Volumes

```bash
# List all volumes
docker volume ls

# Inspect specific volume
docker volume inspect dotnet_transcription-temp
```

### Backup Data

```bash
# Backup logs
docker cp transcription-api:/app/logs ./backup-logs

# Backup temp files
docker cp transcription-api:/app/temp ./backup-temp
```

### Clean Up Volumes

```bash
# Remove all volumes (WARNING: deletes data)
docker-compose down -v

# Remove specific volume
docker volume rm dotnet_transcription-temp
```

## 🔒 Production Deployment

### 1. Use Production Image

```bash
# Build optimized image
docker build \
  --build-arg WHISPER_MODEL_SIZE=medium \
  -t myregistry.com/transcription-api:1.0.0 \
  .

# Push to registry
docker push myregistry.com/transcription-api:1.0.0
```

### 2. Enable HTTPS

Create `docker-compose.prod.yml`:

```yaml
services:
  transcription-api:
    environment:
      - ASPNETCORE_URLS=https://+:5226
      - ASPNETCORE_Kestrel__Certificates__Default__Path=/app/certs/cert.pfx
      - ASPNETCORE_Kestrel__Certificates__Default__Password=${CERT_PASSWORD}
    volumes:
      - ./certs:/app/certs:ro
```

### 3. Add Resource Limits

```yaml
services:
  transcription-api:
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 8G
        reservations:
          cpus: '2.0'
          memory: 4G
```

### 4. Set Up Monitoring

```yaml
services:
  transcription-api:
    labels:
      - "prometheus.scrape=true"
      - "prometheus.port=5226"
      - "prometheus.path=/metrics"
```

## 🧪 Testing

### Run Integration Tests

```bash
# Start the service
docker-compose up -d

# Wait for it to be ready
sleep 10

# Run tests
./build-and-run.sh medium test

# Or manually
curl -X POST http://localhost:5226/api/transcription \
  -F "file=@test-audio.wav" \
  | jq '.'
```

### Performance Testing

```bash
# Install Apache Bench
brew install httpd  # macOS
apt-get install apache2-utils  # Linux

# Run load test
ab -n 100 -c 10 http://localhost:5226/api/health
```

## 🧹 Cleanup

```bash
# Stop and remove containers
docker-compose down

# Remove containers and volumes
docker-compose down -v

# Remove images
docker rmi transcription-api:latest

# Clean up everything Docker
docker system prune -a --volumes
```

## 📚 Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [ASP.NET Core in Docker](https://docs.microsoft.com/en-us/aspnet/core/host-and-deploy/docker/)
- [Whisper.net GitHub](https://github.com/sandrohanea/whisper.net)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)

## 🆘 Getting Help

If you encounter issues:

1. Check the logs: `docker-compose logs -f`
2. Verify configuration: `docker-compose config`
3. Check resource usage: `docker stats`
4. Review the troubleshooting section above
5. Open an issue with logs and configuration details
