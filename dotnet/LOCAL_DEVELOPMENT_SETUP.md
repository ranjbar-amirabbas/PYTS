# Local Development Setup

Complete guide for setting up the ASP.NET Core Transcription API for local development (without Docker).

## Prerequisites

### 1. .NET SDK

Install .NET 10 Preview SDK:

**macOS:**
```bash
# Download from Microsoft
# https://dotnet.microsoft.com/download/dotnet/10.0

# Or use Homebrew (if available)
brew install --cask dotnet-sdk-preview
```

**Linux:**
```bash
# Follow instructions at:
# https://learn.microsoft.com/en-us/dotnet/core/install/linux
```

**Windows:**
```bash
# Download installer from:
# https://dotnet.microsoft.com/download/dotnet/10.0
```

Verify installation:
```bash
dotnet --version
# Should show: 10.0.x
```

### 2. FFmpeg (Required for Audio Processing)

FFmpeg is essential for audio format conversion and processing.

**macOS:**
```bash
# Using Homebrew (recommended)
brew install ffmpeg

# Verify installation
ffmpeg -version
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg

# Verify installation
ffmpeg -version
```

**Linux (Fedora/RHEL):**
```bash
sudo dnf install ffmpeg

# Verify installation
ffmpeg -version
```

**Windows:**
```bash
# Using Chocolatey
choco install ffmpeg

# Or download from: https://ffmpeg.org/download.html
# Add to PATH manually
```

### 3. IDE (Optional but Recommended)

Choose one:
- **Visual Studio 2022** (Windows/Mac) - Full IDE
- **JetBrains Rider** (Cross-platform) - Excellent .NET IDE
- **Visual Studio Code** (Cross-platform) - Lightweight with C# extension

## Quick Start

### 1. Clone and Navigate

```bash
cd dotnet/TranscriptionApi
```

### 2. Restore Dependencies

```bash
dotnet restore
```

### 3. Build Project

```bash
dotnet build
```

### 4. Run Application

```bash
dotnet run
```

The API will start on: http://localhost:5226

### 5. Test the API

```bash
# Health check
curl http://localhost:5226/api/v1/health

# Open Swagger UI
open http://localhost:5226  # macOS
xdg-open http://localhost:5226  # Linux
start http://localhost:5226  # Windows
```

## Configuration

### appsettings.json

Edit `appsettings.json` to customize:

```json
{
  "Transcription": {
    "WhisperModelSize": "medium",
    "MaxConcurrentWorkers": 4,
    "MaxQueueSize": 100,
    "MaxFileSizeMB": 500,
    "JobCleanupMaxAgeHours": 24,
    "StreamMinChunkSize": 102400,
    "StreamMaxBufferSize": 10485760
  }
}
```

### Model Sizes

Choose based on your needs:

| Model | Size | RAM | Speed | Accuracy |
|-------|------|-----|-------|----------|
| tiny | 75MB | 1GB | ⚡⚡⚡⚡⚡ | ⭐⭐ |
| base | 142MB | 1GB | ⚡⚡⚡⚡ | ⭐⭐⭐ |
| small | 466MB | 2GB | ⚡⚡⚡ | ⭐⭐⭐⭐ |
| medium | 1.5GB | 4GB | ⚡⚡ | ⭐⭐⭐⭐⭐ |
| large | 2.9GB | 8GB | ⚡ | ⭐⭐⭐⭐⭐ |

### Environment Variables

Set environment variables for runtime configuration:

**macOS/Linux:**
```bash
export Transcription__WhisperModelSize=small
export Transcription__MaxConcurrentWorkers=2
dotnet run
```

**Windows (PowerShell):**
```powershell
$env:Transcription__WhisperModelSize="small"
$env:Transcription__MaxConcurrentWorkers="2"
dotnet run
```

## Development Workflow

### Watch Mode (Auto-rebuild)

```bash
dotnet watch run
```

This will automatically rebuild and restart when you change code.

### Hot Reload

With .NET 10, hot reload is enabled by default:
```bash
dotnet watch run --no-hot-reload  # Disable if needed
```

### Debug Mode

**Visual Studio / Rider:**
- Press F5 to start debugging
- Set breakpoints in code
- Use debug console

**VS Code:**
1. Install C# extension
2. Open folder in VS Code
3. Press F5 to start debugging

### Run Tests

```bash
# Run all tests
dotnet test

# Run with coverage
dotnet test --collect:"XPlat Code Coverage"

# Run specific test
dotnet test --filter "FullyQualifiedName~HealthControllerTests"
```

## Troubleshooting

### Issue: FFmpeg Not Found

**Error:**
```
System.InvalidOperationException: Audio conversion failed: File not found: ffmpeg
```

**Solution:**
```bash
# macOS
brew install ffmpeg

# Linux
sudo apt install ffmpeg  # Ubuntu/Debian
sudo dnf install ffmpeg  # Fedora/RHEL

# Windows
choco install ffmpeg

# Verify
ffmpeg -version
```

### Issue: Model Download Fails

**Error:**
```
Failed to download Whisper model
```

**Solution:**
```bash
# Pre-download manually
mkdir -p ~/.cache/whisper
cd ~/.cache/whisper

# Download medium model
wget https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin

# Or use curl
curl -L -o ggml-medium.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin
```

### Issue: Port Already in Use

**Error:**
```
Failed to bind to address http://0.0.0.0:5226: address already in use
```

**Solution:**
```bash
# Find process using port
lsof -i :5226  # macOS/Linux
netstat -ano | findstr :5226  # Windows

# Kill process
kill -9 <PID>  # macOS/Linux
taskkill /PID <PID> /F  # Windows

# Or change port in appsettings.json
```

### Issue: Out of Memory

**Error:**
```
OutOfMemoryException during model loading
```

**Solution:**
1. Use smaller model (tiny, base, or small)
2. Close other applications
3. Increase system RAM
4. Reduce MaxConcurrentWorkers

### Issue: Slow Performance

**Symptoms:**
- Transcription takes too long
- High CPU usage
- System becomes unresponsive

**Solutions:**
1. **Use smaller model:**
   ```json
   "WhisperModelSize": "small"
   ```

2. **Reduce workers:**
   ```json
   "MaxConcurrentWorkers": 2
   ```

3. **Check system resources:**
   ```bash
   # macOS
   top
   
   # Linux
   htop
   
   # Windows
   Task Manager
   ```

### Issue: Build Errors

**Error:**
```
error CS0246: The type or namespace name 'X' could not be found
```

**Solution:**
```bash
# Clean and restore
dotnet clean
dotnet restore
dotnet build
```

## Project Structure

```
TranscriptionApi/
├── Controllers/           # API endpoints
│   ├── HealthController.cs
│   ├── TranscriptionController.cs
│   └── StreamingTranscriptionController.cs
├── Services/             # Business logic
│   ├── WhisperModelService.cs
│   ├── TranscriptionService.cs
│   ├── JobManager.cs
│   └── AudioProcessor.cs
├── Middleware/           # Request pipeline
│   ├── GlobalExceptionHandler.cs
│   └── RequestResponseLoggingMiddleware.cs
├── Models/               # Data models
│   ├── AppConfiguration.cs
│   ├── ResponseDTOs.cs
│   └── TranscriptionJob.cs
├── Exceptions/           # Custom exceptions
├── Program.cs            # Application entry point
├── appsettings.json      # Configuration
└── TranscriptionApi.csproj  # Project file
```

## Development Tips

### 1. Use Smaller Model for Development

```json
{
  "Transcription": {
    "WhisperModelSize": "tiny"  // Fast for testing
  }
}
```

### 2. Enable Detailed Logging

```json
{
  "Logging": {
    "LogLevel": {
      "Default": "Debug",
      "Microsoft.AspNetCore": "Information"
    }
  }
}
```

### 3. Use Watch Mode

```bash
dotnet watch run
```

### 4. Test with Sample Audio

```bash
# Create test audio file
ffmpeg -f lavfi -i "sine=frequency=1000:duration=5" -ar 16000 test.wav

# Test transcription
curl -X POST http://localhost:5226/api/v1/transcribe/batch \
  -F "file=@test.wav"
```

### 5. Profile Performance

```bash
# Install dotnet-trace
dotnet tool install --global dotnet-trace

# Collect trace
dotnet-trace collect --process-id <PID>

# Analyze with PerfView or Visual Studio
```

## IDE Setup

### Visual Studio Code

1. Install extensions:
   - C# (Microsoft)
   - C# Dev Kit (Microsoft)
   - REST Client (for testing)

2. Create `.vscode/launch.json`:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": ".NET Core Launch (web)",
      "type": "coreclr",
      "request": "launch",
      "preLaunchTask": "build",
      "program": "${workspaceFolder}/bin/Debug/net10.0/TranscriptionApi.dll",
      "args": [],
      "cwd": "${workspaceFolder}",
      "stopAtEntry": false,
      "serverReadyAction": {
        "action": "openExternally",
        "pattern": "\\bNow listening on:\\s+(https?://\\S+)"
      },
      "env": {
        "ASPNETCORE_ENVIRONMENT": "Development"
      }
    }
  ]
}
```

### JetBrains Rider

1. Open solution file
2. Set run configuration
3. Press F5 to debug

### Visual Studio 2022

1. Open solution file
2. Set TranscriptionApi as startup project
3. Press F5 to debug

## Next Steps

### For Development
- Set up hot reload
- Configure logging
- Add custom middleware
- Write unit tests

### For Testing
- Use Swagger UI for manual testing
- Write integration tests
- Test with various audio formats
- Load test with multiple requests

### For Production
- Review security settings
- Configure HTTPS
- Set up monitoring
- Optimize performance
- Use Docker for deployment

## Additional Resources

- [ASP.NET Core Documentation](https://docs.microsoft.com/en-us/aspnet/core/)
- [Whisper.net GitHub](https://github.com/sandrohanea/whisper.net)
- [FFmpeg Documentation](https://ffmpeg.org/documentation.html)
- [.NET CLI Reference](https://docs.microsoft.com/en-us/dotnet/core/tools/)

## Getting Help

If you encounter issues:

1. Check this troubleshooting guide
2. Review application logs
3. Check FFmpeg installation
4. Verify model files exist
5. Check system resources
6. Open an issue with details
