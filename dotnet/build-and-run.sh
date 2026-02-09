#!/bin/bash

# Build and Run Script for ASP.NET Core Transcription API with Docker
# Usage: ./build-and-run.sh [model_size] [action]
# Example: ./build-and-run.sh medium build
# Example: ./build-and-run.sh small up

set -e

# Default values
MODEL_SIZE="${1:-medium}"
ACTION="${2:-up}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== ASP.NET Core Transcription API - Docker Setup ===${NC}"
echo ""

# Validate model size
case $MODEL_SIZE in
  tiny|base|small|medium|large)
    echo -e "${GREEN}✓ Using model size: ${MODEL_SIZE}${NC}"
    ;;
  *)
    echo -e "${RED}✗ Invalid model size: ${MODEL_SIZE}${NC}"
    echo "Valid options: tiny, base, small, medium, large"
    exit 1
    ;;
esac

# Export for docker-compose
export WHISPER_MODEL_SIZE=$MODEL_SIZE

case $ACTION in
  build)
    echo -e "${YELLOW}Building Docker image...${NC}"
    docker-compose build --build-arg WHISPER_MODEL_SIZE=$MODEL_SIZE
    echo -e "${GREEN}✓ Build complete${NC}"
    ;;
    
  up)
    echo -e "${YELLOW}Starting services...${NC}"
    docker-compose up -d
    echo ""
    echo -e "${GREEN}✓ Services started${NC}"
    echo ""
    echo "API available at: http://localhost:5226"
    echo "Swagger UI: http://localhost:5226"
    echo "Health check: http://localhost:5226/api/health"
    echo ""
    echo "View logs: docker-compose logs -f transcription-api"
    ;;
    
  down)
    echo -e "${YELLOW}Stopping services...${NC}"
    docker-compose down
    echo -e "${GREEN}✓ Services stopped${NC}"
    ;;
    
  restart)
    echo -e "${YELLOW}Restarting services...${NC}"
    docker-compose restart
    echo -e "${GREEN}✓ Services restarted${NC}"
    ;;
    
  logs)
    docker-compose logs -f transcription-api
    ;;
    
  clean)
    echo -e "${YELLOW}Cleaning up...${NC}"
    docker-compose down -v
    docker rmi transcription-api:latest 2>/dev/null || true
    echo -e "${GREEN}✓ Cleanup complete${NC}"
    ;;
    
  test)
    echo -e "${YELLOW}Testing API...${NC}"
    echo ""
    
    # Wait for service to be ready
    echo "Waiting for service to start..."
    sleep 5
    
    # Health check
    echo "Checking health endpoint..."
    curl -s http://localhost:5226/api/health | jq '.' || echo "Health check failed"
    echo ""
    
    echo -e "${GREEN}✓ Test complete${NC}"
    ;;
    
  *)
    echo -e "${RED}✗ Unknown action: ${ACTION}${NC}"
    echo ""
    echo "Available actions:"
    echo "  build   - Build Docker image"
    echo "  up      - Start services"
    echo "  down    - Stop services"
    echo "  restart - Restart services"
    echo "  logs    - View logs"
    echo "  clean   - Remove containers and images"
    echo "  test    - Test API endpoints"
    exit 1
    ;;
esac
