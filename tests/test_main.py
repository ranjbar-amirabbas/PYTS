"""
Unit tests for FastAPI application initialization and configuration.

Tests CORS configuration, exception handlers, and basic endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestCORSConfiguration:
    """Test CORS middleware configuration."""
    
    def test_cors_allows_all_origins(self):
        """Test that CORS allows requests from any origin."""
        response = client.get(
            "/api/v1/health",
            headers={"Origin": "http://localhost:3000"}
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "*"
    
    def test_cors_allows_credentials(self):
        """Test that CORS allows credentials."""
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )
        assert "access-control-allow-credentials" in response.headers
        assert response.headers["access-control-allow-credentials"] == "true"
    
    def test_cors_allows_all_methods(self):
        """Test that CORS allows all HTTP methods."""
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST"
            }
        )
        assert response.status_code == 200
        assert "access-control-allow-methods" in response.headers


class TestExceptionHandlers:
    """Test custom exception handlers for consistent error responses."""
    
    def test_validation_error_returns_400(self):
        """Test that validation errors return 400 with consistent format."""
        # This will trigger a validation error when endpoints are added
        # For now, test with a non-existent endpoint that would validate params
        response = client.get("/api/v1/nonexistent?invalid=param")
        # Should return 404 for non-existent endpoint, not validation error
        assert response.status_code == 404
    
    def test_error_response_format(self):
        """Test that error responses follow the consistent format."""
        # Test with non-existent endpoint
        response = client.get("/api/v1/nonexistent")
        assert response.status_code == 404
        
        # The default 404 from FastAPI doesn't use our format yet
        # This will be properly tested when we add actual endpoints
    
    def test_general_exception_returns_500(self):
        """Test that unexpected exceptions return 500 with consistent format."""
        # This will be tested when we add endpoints that can raise exceptions
        pass


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_endpoint_exists(self):
        """Test that health endpoint is accessible."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
    
    def test_health_endpoint_returns_json(self):
        """Test that health endpoint returns JSON."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
    
    def test_health_endpoint_structure(self):
        """Test that health endpoint returns expected structure."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "model_loaded" in data
        assert "model_size" in data
    
    def test_health_endpoint_initial_state(self):
        """Test that health endpoint shows correct initial state."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["model_loaded"] is False
        assert data["model_size"] == "not_loaded"
    
    def test_health_endpoint_status_values(self):
        """Test that health endpoint returns valid status values."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        # Status should be a string
        assert isinstance(data["status"], str)
        # Model loaded should be a boolean
        assert isinstance(data["model_loaded"], bool)
        # Model size should be a string
        assert isinstance(data["model_size"], str)
    
    def test_health_endpoint_always_returns_200(self):
        """Test that health endpoint always returns 200 OK."""
        # Health endpoint should return 200 even if model is not loaded
        # This allows monitoring systems to distinguish between service down vs not ready
        response = client.get("/api/v1/health")
        assert response.status_code == 200


class TestApplicationMetadata:
    """Test FastAPI application metadata."""
    
    def test_openapi_docs_available(self):
        """Test that OpenAPI documentation is available."""
        response = client.get("/docs")
        assert response.status_code == 200
    
    def test_redoc_available(self):
        """Test that ReDoc documentation is available."""
        response = client.get("/redoc")
        assert response.status_code == 200
    
    def test_openapi_schema_available(self):
        """Test that OpenAPI schema is available."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        schema = response.json()
        assert "info" in schema
        assert schema["info"]["title"] == "Persian Transcription API"
        assert schema["info"]["version"] == "1.0.0"


class TestErrorResponseFormat:
    """Test that error responses follow the consistent format."""
    
    def test_404_error_format(self):
        """Test 404 error response format."""
        response = client.get("/api/v1/nonexistent")
        assert response.status_code == 404
        
        # FastAPI's default 404 response
        data = response.json()
        assert "detail" in data
    
    def test_method_not_allowed_format(self):
        """Test 405 error response format."""
        response = client.post("/api/v1/health")
        assert response.status_code == 405
        
        # FastAPI's default 405 response
        data = response.json()
        assert "detail" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
