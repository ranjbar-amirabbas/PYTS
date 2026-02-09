#!/bin/bash

# Test Script for Docker-based Transcription API
# Tests health endpoint and basic functionality

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

API_URL="http://localhost:5226"
MAX_RETRIES=30
RETRY_DELAY=2

echo -e "${YELLOW}=== Testing Transcription API in Docker ===${NC}\n"

# Function to wait for API to be ready
wait_for_api() {
    echo "Waiting for API to be ready..."
    for i in $(seq 1 $MAX_RETRIES); do
        if curl -s -f "${API_URL}/api/health" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ API is ready${NC}\n"
            return 0
        fi
        echo -n "."
        sleep $RETRY_DELAY
    done
    echo -e "\n${RED}✗ API failed to start after ${MAX_RETRIES} attempts${NC}"
    return 1
}

# Test 1: Health Check
test_health() {
    echo "Test 1: Health Check"
    echo "-------------------"
    
    response=$(curl -s "${API_URL}/api/health")
    
    if echo "$response" | jq -e '.status == "Healthy"' > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Health check passed${NC}"
        echo "Response: $response" | jq '.'
        return 0
    else
        echo -e "${RED}✗ Health check failed${NC}"
        echo "Response: $response"
        return 1
    fi
}

# Test 2: Model Status
test_model() {
    echo -e "\nTest 2: Model Status"
    echo "-------------------"
    
    response=$(curl -s "${API_URL}/api/health")
    
    if echo "$response" | jq -e '.modelLoaded == true' > /dev/null 2>&1; then
        model_size=$(echo "$response" | jq -r '.modelSize')
        echo -e "${GREEN}✓ Model loaded successfully${NC}"
        echo "Model size: $model_size"
        return 0
    else
        echo -e "${RED}✗ Model not loaded${NC}"
        return 1
    fi
}

# Test 3: Swagger UI
test_swagger() {
    echo -e "\nTest 3: Swagger UI"
    echo "-------------------"
    
    if curl -s -f "${API_URL}/" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Swagger UI accessible${NC}"
        echo "URL: ${API_URL}/"
        return 0
    else
        echo -e "${RED}✗ Swagger UI not accessible${NC}"
        return 1
    fi
}

# Test 4: API Endpoints
test_endpoints() {
    echo -e "\nTest 4: API Endpoints"
    echo "-------------------"
    
    endpoints=(
        "/api/health"
        "/api/transcription"
    )
    
    for endpoint in "${endpoints[@]}"; do
        if curl -s -f -X OPTIONS "${API_URL}${endpoint}" > /dev/null 2>&1 || \
           curl -s "${API_URL}${endpoint}" > /dev/null 2>&1; then
            echo -e "${GREEN}✓${NC} ${endpoint}"
        else
            echo -e "${YELLOW}?${NC} ${endpoint} (may require authentication)"
        fi
    done
}

# Main execution
main() {
    # Wait for API
    if ! wait_for_api; then
        echo -e "\n${RED}Tests aborted - API not available${NC}"
        exit 1
    fi
    
    # Run tests
    passed=0
    failed=0
    
    if test_health; then ((passed++)); else ((failed++)); fi
    if test_model; then ((passed++)); else ((failed++)); fi
    if test_swagger; then ((passed++)); else ((failed++)); fi
    test_endpoints
    
    # Summary
    echo -e "\n${YELLOW}=== Test Summary ===${NC}"
    echo -e "Passed: ${GREEN}${passed}${NC}"
    echo -e "Failed: ${RED}${failed}${NC}"
    
    if [ $failed -eq 0 ]; then
        echo -e "\n${GREEN}✓ All tests passed!${NC}"
        exit 0
    else
        echo -e "\n${RED}✗ Some tests failed${NC}"
        exit 1
    fi
}

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo -e "${YELLOW}Warning: jq not installed. Install with: brew install jq${NC}\n"
fi

main
