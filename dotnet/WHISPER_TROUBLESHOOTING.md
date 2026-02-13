# Whisper.net Troubleshooting Guide

## "Failed to encode audio features" Error

This error typically occurs due to:

### 1. Runtime Package Mismatch
- **Issue**: Using `Whisper.net.Runtime.CoreML` in Linux Docker containers
- **Solution**: Remove CoreML package, use only `Whisper.net.Runtime` for Linux
- **Fixed in**: TranscriptionApi.csproj

### 2. Missing Native Dependencies
- **Issue**: Missing libgomp1 or other required libraries
- **Solution**: Install libgomp1 in Dockerfile
- **Fixed in**: Dockerfile base stage

### 3. Model File Issues
- **Issue**: Corrupted or incompatible model file
- **Solution**: 
  - Delete cached model: `rm -rf ~/.cache/whisper/*`
  - Rebuild Docker image to re-download model
  - Verify model file size (should be >100MB)

### 4. Architecture Mismatch
- **Issue**: Running on ARM when built for x86 or vice versa
- **Solution**: Build for correct platform using `--platform linux/amd64`

## Rebuild Instructions

After fixes, rebuild the Docker image:

```bash
cd dotnet
docker-compose down
docker-compose build --no-cache
docker-compose up
```

## Verify Model Loading

Check logs for:
```
Model loading: SYSTEM_INFO - OS: ..., Architecture: ..., ProcessorCount: ...
Model loading: COMPLETED - ModelSize: large, TotalDuration: ...
```

## Test Transcription

```bash
curl -X POST http://localhost:5226/api/v1/transcribe/sync \
  -F "audioFile=@test.mp3"
```
