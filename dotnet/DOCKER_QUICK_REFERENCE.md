# Docker Quick Reference

## 🚀 Quick Commands

### Start/Stop

```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# Restart
docker-compose restart

# Stop and remove volumes
docker-compose down -v
```

### Logs

```bash
# Follow logs
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100

# Specific service
docker-compose logs -f transcription-api
```

### Build

```bash
# Build with default (medium) model
docker-compose build

# Build with specific model
docker-compose build --build-arg WHISPER_MODEL_SIZE=small

# Force rebuild (no cache)
docker-compose build --no-cache
```

### Testing

```bash
# Health check
curl http://localhost:5226/api/health

# Run test script
./test-docker.sh

# Transcribe audio
curl -X POST http://localhost:5226/api/transcription \
  -F "file=@audio.wav"
```

### Debugging

```bash
# Enter container shell
docker-compose exec transcription-api bash

# Check running processes
docker-compose ps

# View resource usage
docker stats transcription-api

# Inspect container
docker inspect transcription-api
```

### Cleanup

```bash
# Remove stopped containers
docker-compose rm

# Remove all (containers + volumes)
docker-compose down -v

# Clean Docker system
docker system prune -a --volumes
```

## 📊 Model Sizes

| Model | Command | Size | RAM |
|-------|---------|------|-----|
| tiny | `WHISPER_MODEL_SIZE=tiny` | 75MB | 1GB |
| base | `WHISPER_MODEL_SIZE=base` | 142MB | 1GB |
| small | `WHISPER_MODEL_SIZE=small` | 466MB | 2GB |
| medium | `WHISPER_MODEL_SIZE=medium` | 1.5GB | 4GB |
| large | `WHISPER_MODEL_SIZE=large` | 2.9GB | 8GB |

## 🔧 Common Tasks

### Change Port

Edit `docker-compose.yml`:
```yaml
ports:
  - "5227:5226"  # Host:Container
```

### Change Model

```bash
# Rebuild with different model
docker-compose build --build-arg WHISPER_MODEL_SIZE=small
docker-compose up -d
```

### View Model Files

```bash
docker-compose exec transcription-api ls -lh /root/.cache/whisper
```

### Backup Logs

```bash
docker cp transcription-api:/app/logs ./backup-logs
```

### Update Image

```bash
docker-compose pull
docker-compose up -d
```

## 🐛 Troubleshooting

### Port in Use
```bash
lsof -i :5226
kill -9 <PID>
```

### Out of Memory
```bash
# Increase Docker memory (Docker Desktop → Settings)
# Or use smaller model
WHISPER_MODEL_SIZE=small docker-compose up -d
```

### Container Won't Start
```bash
docker-compose logs transcription-api
docker-compose restart
```

### Slow Performance
```bash
# Check resources
docker stats

# Reduce workers in docker-compose.yml
environment:
  - Transcription__MaxConcurrentWorkers=2
```

## 📍 Important URLs

- **API**: http://localhost:5226
- **Swagger**: http://localhost:5226
- **Health**: http://localhost:5226/api/health

## 📁 Important Paths

- **Logs**: `/app/logs`
- **Temp**: `/app/temp`
- **Models**: `/root/.cache/whisper`
- **Config**: `/app/appsettings.json`

## 🔑 Environment Variables

```bash
# Set in docker-compose.yml
environment:
  - Transcription__WhisperModelSize=medium
  - Transcription__MaxConcurrentWorkers=4
  - Transcription__MaxQueueSize=100
  - Transcription__MaxFileSizeMB=500
```

## 📦 Helper Scripts

```bash
# Build and run
./build-and-run.sh medium up

# View logs
./build-and-run.sh medium logs

# Run tests
./test-docker.sh

# Clean up
./build-and-run.sh medium clean
```
