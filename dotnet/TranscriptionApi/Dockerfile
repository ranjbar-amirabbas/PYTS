# ASP.NET Core Transcription API - Multi-stage Docker Build
# This Dockerfile creates a production image with Whisper.net and all dependencies

# =============================================================================
# Base Stage: Runtime Dependencies
# =============================================================================
FROM mcr.microsoft.com/dotnet/aspnet:10.0-preview AS base

# Install FFmpeg and required libraries for Whisper.net
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
EXPOSE 5226

# =============================================================================
# Build Stage: Compile Application
# =============================================================================
FROM mcr.microsoft.com/dotnet/sdk:10.0-preview AS build

WORKDIR /src

# Copy project file and restore dependencies
COPY ["TranscriptionApi.csproj", "./"]
RUN dotnet restore "TranscriptionApi.csproj"

# Copy source code and build
COPY . .
RUN dotnet build "TranscriptionApi.csproj" -c Release -o /app/build

# =============================================================================
# Publish Stage: Create Optimized Output
# =============================================================================
FROM build AS publish
RUN dotnet publish "TranscriptionApi.csproj" -c Release -o /app/publish /p:UseAppHost=false

# =============================================================================
# Model Download Stage: Pre-download Whisper Model
# =============================================================================
FROM base AS model-download

# Install wget for downloading models
RUN apt-get update && apt-get install -y wget && rm -rf /var/lib/apt/lists/*

# Create cache directory
RUN mkdir -p /root/.cache/whisper

# Download Whisper model at build time (default: medium)
ARG WHISPER_MODEL_SIZE=medium
ENV WHISPER_MODEL_SIZE=${WHISPER_MODEL_SIZE}

# Download the GGML model from Hugging Face
# Note: Using the correct model URLs for Whisper.net compatibility
RUN case "$WHISPER_MODEL_SIZE" in \
        "tiny") \
            wget -O /root/.cache/whisper/ggml-tiny.bin \
            https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin \
            ;; \
        "base") \
            wget -O /root/.cache/whisper/ggml-base.bin \
            https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin \
            ;; \
        "small") \
            wget -O /root/.cache/whisper/ggml-small.bin \
            https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin \
            ;; \
        "medium") \
            wget -O /root/.cache/whisper/ggml-medium.bin \
            https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin \
            ;; \
        "large") \
            wget -O /root/.cache/whisper/ggml-large.bin \
            https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin \
            ;; \
        *) \
            echo "Invalid WHISPER_MODEL_SIZE: $WHISPER_MODEL_SIZE" && exit 1 \
            ;; \
    esac

# =============================================================================
# Final Stage: Production Image
# =============================================================================
FROM base AS final

# Copy published application
COPY --from=publish /app/publish .

# Copy pre-downloaded Whisper model
COPY --from=model-download /root/.cache/whisper /root/.cache/whisper

# Create directories for temporary files
RUN mkdir -p /app/temp /app/logs

# Set environment variables
ENV ASPNETCORE_URLS=http://+:5226
ENV ASPNETCORE_ENVIRONMENT=Production
ENV Transcription__WhisperModelSize=medium
ENV Transcription__MaxConcurrentWorkers=4
ENV Transcription__MaxQueueSize=100
ENV Transcription__MaxFileSizeMB=500
ENV Transcription__JobCleanupMaxAgeHours=24

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5226/api/health || exit 1

ENTRYPOINT ["dotnet", "TranscriptionApi.dll"]
