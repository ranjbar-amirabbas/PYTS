# Docker Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Docker Host                              │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              transcription-api Container                    │ │
│  │                                                             │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │         ASP.NET Core Application                     │  │ │
│  │  │                                                       │  │ │
│  │  │  ┌─────────────────┐  ┌──────────────────┐          │  │ │
│  │  │  │  Controllers    │  │   Middleware     │          │  │ │
│  │  │  │  - Health       │  │   - Logging      │          │  │ │
│  │  │  │  - Transcription│  │   - Exception    │          │  │ │
│  │  │  │  - Streaming    │  │   - CORS         │          │  │ │
│  │  │  └────────┬────────┘  └────────┬─────────┘          │  │ │
│  │  │           │                    │                     │  │ │
│  │  │           └────────┬───────────┘                     │  │ │
│  │  │                    ▼                                 │  │ │
│  │  │  ┌──────────────────────────────────────┐           │  │ │
│  │  │  │         Services Layer               │           │  │ │
│  │  │  │  - TranscriptionService              │           │  │ │
│  │  │  │  - JobManager                        │           │  │ │
│  │  │  │  - AudioProcessor                    │           │  │ │
│  │  │  │  - WhisperModelService               │           │  │ │
│  │  │  └──────────────┬───────────────────────┘           │  │ │
│  │  │                 │                                    │  │ │
│  │  └─────────────────┼────────────────────────────────────┘  │ │
│  │                    │                                        │ │
│  │  ┌─────────────────▼────────────────────────────────────┐  │ │
│  │  │         Whisper.net Library                          │  │ │
│  │  │  - WhisperFactory                                    │  │ │
│  │  │  - WhisperProcessor                                  │  │ │
│  │  │  - Native Runtime (libwhisper.dylib)                 │  │ │
│  │  └──────────────┬───────────────────────────────────────┘  │ │
│  │                 │                                           │ │
│  │  ┌──────────────▼───────────────────────────────────────┐  │ │
│  │  │         Whisper Model (GGML)                         │  │ │
│  │  │  Location: /root/.cache/whisper/ggml-medium.bin     │  │ │
│  │  │  Size: ~1.5GB (medium model)                         │  │ │
│  │  │  Pre-downloaded at build time                        │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  │                                                             │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │         FFmpeg                                        │  │ │
│  │  │  - Audio format conversion (MP3, WAV, etc.)          │  │ │
│  │  │  - Audio resampling (16kHz)                          │  │ │
│  │  │  - Audio validation                                  │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  │                                                             │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │         File System                                   │  │ │
│  │  │  /app/temp     - Temporary audio files               │  │ │
│  │  │  /app/logs     - Application logs                    │  │ │
│  │  │  /root/.cache  - Model cache                         │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  │                                                             │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    Docker Volumes                          │ │
│  │  - transcription-temp  (mounted to /app/temp)             │ │
│  │  - transcription-logs  (mounted to /app/logs)             │ │
│  │  - ~/.cache/whisper    (mounted to /root/.cache/whisper)  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    Docker Network                          │ │
│  │  - transcription-network (bridge)                         │ │
│  │  - Port mapping: 5226:5226                                │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   External Access    │
                    │  http://localhost:5226│
                    │  - REST API          │
                    │  - Swagger UI        │
                    │  - Health Checks     │
                    └──────────────────────┘
```

## Build Process Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Docker Build Process                          │
└─────────────────────────────────────────────────────────────────┘

Stage 1: Base
┌──────────────────────────────────────┐
│ mcr.microsoft.com/dotnet/aspnet:10.0 │
│ + FFmpeg installation                │
│ + Working directory setup            │
└──────────────┬───────────────────────┘
               │
               ▼
Stage 2: Build
┌──────────────────────────────────────┐
│ mcr.microsoft.com/dotnet/sdk:10.0    │
│ + Copy .csproj                       │
│ + Restore NuGet packages             │
│ + Copy source code                   │
│ + Build application                  │
└──────────────┬───────────────────────┘
               │
               ▼
Stage 3: Publish
┌──────────────────────────────────────┐
│ Publish optimized release build      │
│ + AOT compilation (if enabled)       │
│ + Trimming unused code               │
│ + Output to /app/publish             │
└──────────────┬───────────────────────┘
               │
               ▼
Stage 4: Model Download
┌──────────────────────────────────────┐
│ Download Whisper model from HF       │
│ + wget ggml-{size}.bin               │
│ + Save to /root/.cache/whisper       │
│ + Validate download                  │
└──────────────┬───────────────────────┘
               │
               ▼
Stage 5: Final
┌──────────────────────────────────────┐
│ Copy from previous stages:           │
│ + Published app from Stage 3         │
│ + Model files from Stage 4           │
│ + Runtime from Stage 1               │
│ = Minimal production image           │
└──────────────────────────────────────┘
```

## Request Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    HTTP Request Flow                             │
└─────────────────────────────────────────────────────────────────┘

Client Request
     │
     ▼
┌─────────────────────┐
│  Docker Network     │
│  Port 5226          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  Kestrel Web Server                 │
│  - HTTPS/HTTP handling              │
│  - Connection management            │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  Middleware Pipeline                │
│  1. Request Logging                 │
│  2. Exception Handling              │
│  3. CORS                            │
│  4. Authentication (if enabled)     │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  Controller                         │
│  - Route matching                   │
│  - Model binding                    │
│  - Validation                       │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  Service Layer                      │
│  - Business logic                   │
│  - Job management                   │
│  - Audio processing                 │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  WhisperModelService                │
│  - Load model (if not loaded)       │
│  - Queue transcription job          │
│  - Process audio with Whisper       │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  Whisper.net                        │
│  - Native library invocation        │
│  - Audio processing                 │
│  - Text generation                  │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  Response                           │
│  - JSON serialization               │
│  - Response logging                 │
│  - Return to client                 │
└─────────────────────────────────────┘
```

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Transcription Data Flow                       │
└─────────────────────────────────────────────────────────────────┘

Audio File Upload
     │
     ▼
┌─────────────────────┐
│  Temp Storage       │
│  /app/temp/         │
│  (Docker Volume)    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  Audio Validation                   │
│  - Format check                     │
│  - Size check                       │
│  - Duration check                   │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  FFmpeg Processing                  │
│  - Convert to WAV                   │
│  - Resample to 16kHz                │
│  - Mono channel                     │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  Job Queue                          │
│  - Create job ID                    │
│  - Queue for processing             │
│  - Return job ID to client          │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  Whisper Processing                 │
│  - Load audio into memory           │
│  - Process with model               │
│  - Generate transcription           │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  Result Storage                     │
│  - Store transcription text         │
│  - Update job status                │
│  - Clean up temp files              │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────┐
│  Client Response    │
│  - Job status       │
│  - Transcription    │
│  - Metadata         │
└─────────────────────┘
```

## Resource Management

```
┌─────────────────────────────────────────────────────────────────┐
│                    Resource Allocation                           │
└─────────────────────────────────────────────────────────────────┘

CPU
├── Kestrel Web Server (1 core)
├── Worker Threads (2-4 cores)
│   ├── Transcription Worker 1
│   ├── Transcription Worker 2
│   ├── Transcription Worker 3
│   └── Transcription Worker 4
└── Background Tasks (0.5 core)
    ├── Job Cleanup
    └── Health Monitoring

Memory
├── .NET Runtime (500MB)
├── Whisper Model (1.5GB - medium)
├── Audio Buffers (100MB per job)
├── Job Queue (50MB)
└── Overhead (350MB)
Total: ~4GB for medium model

Disk
├── Application (100MB)
├── Whisper Model (1.5GB)
├── Temp Files (varies)
└── Logs (grows over time)
Total: ~2GB + temp files

Network
├── Incoming: HTTP/HTTPS on port 5226
├── Outgoing: Model download (build time only)
└── Internal: Docker bridge network
```

## Deployment Scenarios

### Single Container (Development)
```
┌──────────────────────┐
│   Docker Container   │
│  transcription-api   │
│   Port: 5226         │
└──────────────────────┘
```

### Docker Compose (Local/Testing)
```
┌──────────────────────────────────┐
│      Docker Compose              │
│  ┌────────────────────────────┐  │
│  │  transcription-api         │  │
│  │  + Volumes                 │  │
│  │  + Networks                │  │
│  │  + Health Checks           │  │
│  └────────────────────────────┘  │
└──────────────────────────────────┘
```

### Production (Kubernetes)
```
┌─────────────────────────────────────────┐
│         Kubernetes Cluster              │
│  ┌───────────────────────────────────┐  │
│  │  Ingress Controller               │  │
│  │  (Load Balancer)                  │  │
│  └──────────────┬────────────────────┘  │
│                 │                        │
│  ┌──────────────▼────────────────────┐  │
│  │  Service (ClusterIP)              │  │
│  └──────────────┬────────────────────┘  │
│                 │                        │
│  ┌──────────────▼────────────────────┐  │
│  │  Deployment                       │  │
│  │  ┌──────────┐  ┌──────────┐      │  │
│  │  │  Pod 1   │  │  Pod 2   │      │  │
│  │  │  API     │  │  API     │      │  │
│  │  └──────────┘  └──────────┘      │  │
│  └───────────────────────────────────┘  │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  Persistent Volumes               │  │
│  │  - Model Cache                    │  │
│  │  - Logs                           │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

This architecture provides a scalable, maintainable, and production-ready solution for running the Transcription API with Whisper.net in Docker.
