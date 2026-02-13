#!/bin/bash

# Script to rebuild .NET Transcription API with Whisper.net fixes
# This addresses the "Failed to encode audio features" error

set -e

echo "=========================================="
echo "Rebuilding .NET Transcription API"
echo "=========================================="
echo ""

# Stop and remove existing containers
echo "1. Stopping existing containers..."
docker-compose down

# Remove cached model files to force re-download
echo ""
echo "2. Cleaning cached Whisper models..."
rm -rf ~/.cache/whisper/*

# Rebuild without cache to ensure all changes are applied
echo ""
echo "3. Rebuilding Docker image (this may take several minutes)..."
docker-compose build --no-cache dotnet-transcription-api

# Start the service
echo ""
echo "4. Starting service..."
docker-compose up -d dotnet-transcription-api

# Wait for service to be ready
echo ""
echo "5. Waiting for service to be ready..."
sleep 10

# Show logs
echo ""
echo "6. Showing logs (press Ctrl+C to exit)..."
echo "   Look for: 'Model loading: COMPLETED'"
echo ""
docker-compose logs -f dotnet-transcription-api
