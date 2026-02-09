"""
Integration tests for health check endpoint.

Tests the health check endpoint behavior with different service states.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from app.main import app
from app.transcription_service import TranscriptionService

client = TestClient(app)


class TestHealthCheckIntegration:
    """Integration tests for health check endpoint."""
    
    def test_health_check_with_uninitialized_service(self):
        """Test health check when service is not initialized."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["model_loaded"] is False
        assert data["model_size"] == "not_loaded"
    
    @patch('app.main.transcription_service')
    def test_health_check_with_initialized_service(self, mock_service):
        """Test health check when service is initialized with model loaded."""
        # Mock the transcription service
        mock_service.is_ready.return_value = True
        mock_service.whisper_engine.model_size = "medium"
        
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["model_loaded"] is True
        assert data["model_size"] == "medium"
    
    @patch('app.main.transcription_service')
    def test_health_check_with_service_not_ready(self, mock_service):
        """Test health check when service exists but model is not loaded."""
        # Mock the transcription service
        mock_service.is_ready.return_value = False
        mock_service.whisper_engine.model_size = "not_loaded"
        
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["model_loaded"] is False
    
    def test_health_check_response_schema(self):
        """Test that health check response matches the expected schema."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify all required fields are present
        required_fields = ["status", "model_loaded", "model_size"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Verify field types
        assert isinstance(data["status"], str)
        assert isinstance(data["model_loaded"], bool)
        assert isinstance(data["model_size"], str)
    
    def test_health_check_multiple_calls(self):
        """Test that health check can be called multiple times."""
        # Call health check multiple times
        for _ in range(5):
            response = client.get("/api/v1/health")
            assert response.status_code == 200
            
            data = response.json()
            assert "status" in data
            assert "model_loaded" in data
            assert "model_size" in data
    
    def test_health_check_concurrent_calls(self):
        """Test that health check handles concurrent calls correctly."""
        import concurrent.futures
        
        def call_health_check():
            response = client.get("/api/v1/health")
            return response.status_code, response.json()
        
        # Make 10 concurrent calls
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(call_health_check) for _ in range(10)]
            results = [future.result() for future in futures]
        
        # All calls should succeed
        for status_code, data in results:
            assert status_code == 200
            assert "status" in data
            assert "model_loaded" in data
            assert "model_size" in data
    
    def test_health_check_with_query_params(self):
        """Test that health check ignores query parameters."""
        response = client.get("/api/v1/health?extra=param")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
    
    def test_health_check_content_type(self):
        """Test that health check returns correct content type."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]
    
    def test_health_check_no_authentication_required(self):
        """Test that health check does not require authentication."""
        # Health check should be accessible without any authentication
        response = client.get("/api/v1/health")
        assert response.status_code == 200
    
    @patch('app.main.transcription_service', None)
    def test_health_check_when_service_is_none(self):
        """Test health check when transcription service is None."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["model_loaded"] is False
        assert data["model_size"] == "not_loaded"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
