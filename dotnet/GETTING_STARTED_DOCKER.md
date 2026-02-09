# Getting Started with Docker

## Complete Setup in 5 Minutes

### Step 1: Prerequisites Check

```bash
# Check Docker is installed
docker --version
# Should show: Docker version 20.10+

# Check Docker Compose
docker-compose --version
# Should show: Docker Compose version 2.0+

# Check available disk space (need 4GB+)
df -h
```

### Step 2: Navigate to Project

```bash
cd dotnet
```

### Step 3: Build and Start

```bash
# Option A: Using Docker Compose (Recommended)
docker-compose up -d

# Option B: Using Helper Script
./build-and-run.sh medium up

# Option C: Manual Build
cd TranscriptionApi
docker build -t transcription-api .
docker run -d -p 5226:5226 transcription-api
```

### Step 4: Wait for Startup

The first time will take 2-3 minutes to download the Whisper model.

```bash
# Watch the logs
docker-compose logs -f transcription-api

# Wait for this message:
# "Whisper model preloaded successfully"
```

### Step 5: Test the API

```bash
# Check health
curl http://localhost:5226/api/health

# Expected response:
# {
#   "status": "Healthy",
#   "modelLoaded": true,
#   "modelSize": "medium"
# }
```

### Step 6: Use the API

```bash
# Open Swagger UI in browser
open http://localhost:5226

# Or test with curl
curl -X POST http://localhost:5226/api/transcription \
  -F "file=@your-audio.wav"
```

## What Just Happened?

1. **Docker built the image** (~5 minutes first time)
   - Compiled .NET application
   - Downloaded Whisper model (1.5GB for medium)
   - Installed FFmpeg for audio processing
   - Created optimized production image

2. **Container started** (~30 seconds)
   - Loaded Whisper model into memory
   - Started ASP.NET Core web server
   - Enabled health checks
   - Ready to accept requests

3. **API is now running**
   - Listening on port 5226
   - Swagger UI available
   - Ready to transcribe audio

## Next Steps

### Development

```bash
# View logs in real-time
docker-compose logs -f

# Make changes to code
# Rebuild and restart
docker-compose up -d --build

# Run tests
./test-docker.sh
```

### Production

```bash
# Build with specific model
docker build --build-arg WHISPER_MODEL_SIZE=small -t transcription-api:1.0.0 .

# Tag for registry
docker tag transcription-api:1.0.0 myregistry.com/transcription-api:1.0.0

# Push to registry
docker push myregistry.com/transcription-api:1.0.0

# Deploy to production
docker run -d \
  --name transcription-api \
  -p 5226:5226 \
  --restart unless-stopped \
  myregistry.com/transcription-api:1.0.0
```

### Cleanup

```bash
# Stop services
docker-compose down

# Remove everything including volumes
docker-compose down -v

# Remove images
docker rmi transcription-api:latest
```

## Common Issues

### "Port 5226 already in use"

```bash
# Find and kill the process
lsof -i :5226
kill -9 <PID>

# Or change the port
# Edit docker-compose.yml: ports: - "5227:5226"
```

### "Out of memory"

```bash
# Increase Docker memory
# Docker Desktop → Settings → Resources → Memory (set to 4GB+)

# Or use smaller model
docker-compose build --build-arg WHISPER_MODEL_SIZE=small
```

### "Model download failed"

```bash
# Pre-download manually
mkdir -p ~/.cache/whisper
cd ~/.cache/whisper
wget https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin

# Rebuild
docker-compose build --no-cache
```

## Tips

1. **First build is slow** - Model download takes time, but it's cached
2. **Use smaller models for testing** - `tiny` or `base` are much faster
3. **Check logs if issues** - `docker-compose logs -f` shows everything
4. **Health check is your friend** - Always check `/api/health` first
5. **Volumes persist data** - Logs and temp files survive restarts

## Resources

- **Quick Reference**: See `DOCKER_QUICK_REFERENCE.md`
- **Detailed Guide**: See `README_DOCKER.md`
- **Setup Guide**: See `DOCKER_SETUP.md`
- **Integration Summary**: See `DOCKER_INTEGRATION_SUMMARY.md`

## Success Checklist

- [ ] Docker and Docker Compose installed
- [ ] Project cloned and in `dotnet` directory
- [ ] `docker-compose up -d` completed successfully
- [ ] Health check returns "Healthy"
- [ ] Swagger UI accessible at http://localhost:5226
- [ ] Test transcription works

## You're Ready! 🎉

Your Transcription API is now running in Docker with Whisper.net. You can:

- Transcribe audio files via REST API
- Use Swagger UI for interactive testing
- Scale with Docker Compose or Kubernetes
- Deploy to any cloud platform

For more details, see the other documentation files in this directory.
