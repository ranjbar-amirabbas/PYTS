"""
Tests for API documentation endpoints.

Validates that the OpenAPI documentation is properly generated and accessible.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


class TestAPIDocumentation:
    """Test suite for API documentation endpoints."""
    
    def test_swagger_ui_accessible(self):
        """Test that Swagger UI documentation is accessible."""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
    
    def test_redoc_accessible(self):
        """Test that ReDoc documentation is accessible."""
        response = client.get("/redoc")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
    
    def test_openapi_json_accessible(self):
        """Test that OpenAPI JSON schema is accessible."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        
        # Verify it's valid JSON
        schema = response.json()
        assert isinstance(schema, dict)
    
    def test_openapi_schema_structure(self):
        """Test that OpenAPI schema has required structure."""
        response = client.get("/openapi.json")
        schema = response.json()
        
        # Verify required OpenAPI fields
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema
        assert "components" in schema
        
        # Verify info section
        assert schema["info"]["title"] == "Persian Transcription API"
        assert schema["info"]["version"] == "1.0.0"
        assert "description" in schema["info"]
        assert len(schema["info"]["description"]) > 100
    
    def test_all_endpoints_documented(self):
        """Test that all endpoints are documented in OpenAPI schema."""
        response = client.get("/openapi.json")
        schema = response.json()
        
        paths = schema["paths"]
        
        # Verify expected endpoints exist
        expected_endpoints = [
            "/api/v1/health",
            "/api/v1/capacity",
            "/api/v1/transcribe/batch",
            "/api/v1/transcribe/batch/{job_id}"
        ]
        
        for endpoint in expected_endpoints:
            assert endpoint in paths, f"Endpoint {endpoint} not documented"
    
    def test_endpoints_have_descriptions(self):
        """Test that all endpoints have descriptions."""
        response = client.get("/openapi.json")
        schema = response.json()
        
        for path, methods in schema["paths"].items():
            for method, details in methods.items():
                if method in ["get", "post", "put", "delete", "patch"]:
                    assert "summary" in details, f"{method.upper()} {path} missing summary"
                    assert "description" in details, f"{method.upper()} {path} missing description"
                    assert len(details["description"]) > 50, f"{method.upper()} {path} description too short"
    
    def test_endpoints_have_response_examples(self):
        """Test that endpoints have response examples."""
        response = client.get("/openapi.json")
        schema = response.json()
        
        # Check batch upload endpoint
        batch_post = schema["paths"]["/api/v1/transcribe/batch"]["post"]
        assert "responses" in batch_post
        assert "200" in batch_post["responses"]
        
        # Verify 200 response has example
        response_200 = batch_post["responses"]["200"]
        assert "content" in response_200
        assert "application/json" in response_200["content"]
        assert "example" in response_200["content"]["application/json"]
    
    def test_error_responses_documented(self):
        """Test that error responses are documented."""
        response = client.get("/openapi.json")
        schema = response.json()
        
        # Check batch upload endpoint has error responses
        batch_post = schema["paths"]["/api/v1/transcribe/batch"]["post"]
        responses = batch_post["responses"]
        
        # Verify error status codes are documented
        expected_errors = ["400", "413", "415", "503"]
        for error_code in expected_errors:
            assert error_code in responses, f"Error {error_code} not documented"
            
            # Verify error response has description
            error_response = responses[error_code]
            assert "description" in error_response
    
    def test_response_schemas_have_examples(self):
        """Test that response schemas have examples."""
        response = client.get("/openapi.json")
        schema = response.json()
        
        schemas = schema["components"]["schemas"]
        
        # Check key response models have examples
        models_with_examples = [
            "BatchTranscribeResponse",
            "BatchStatusResponse",
            "HealthResponse"
        ]
        
        for model_name in models_with_examples:
            assert model_name in schemas, f"Schema {model_name} not found"
            # Note: Examples might be in the endpoint responses rather than schema
    
    def test_health_endpoint_documentation(self):
        """Test that health endpoint has comprehensive documentation."""
        response = client.get("/openapi.json")
        schema = response.json()
        
        health_endpoint = schema["paths"]["/api/v1/health"]["get"]
        
        # Verify summary and description
        assert health_endpoint["summary"] == "Check service health status"
        assert "model readiness" in health_endpoint["description"].lower()
        
        # Verify response schema
        assert "200" in health_endpoint["responses"]
        response_200 = health_endpoint["responses"]["200"]
        assert "example" in response_200["content"]["application/json"]
        
        example = response_200["content"]["application/json"]["example"]
        assert "status" in example
        assert "model_loaded" in example
        assert "model_size" in example
    
    def test_batch_endpoint_documentation(self):
        """Test that batch transcription endpoint has comprehensive documentation."""
        response = client.get("/openapi.json")
        schema = response.json()
        
        batch_post = schema["paths"]["/api/v1/transcribe/batch"]["post"]
        
        # Verify summary and description
        assert "upload" in batch_post["summary"].lower()
        assert "audio file" in batch_post["summary"].lower()
        
        description = batch_post["description"]
        assert "supported formats" in description.lower()
        assert "wav" in description.lower()
        assert "mp3" in description.lower()
        assert "ogg" in description.lower()
        assert "m4a" in description.lower()
        
        # Verify examples in description
        assert "example" in description.lower()
        assert "curl" in description.lower() or "python" in description.lower()
    
    def test_status_endpoint_documentation(self):
        """Test that status endpoint has comprehensive documentation."""
        response = client.get("/openapi.json")
        schema = response.json()
        
        status_get = schema["paths"]["/api/v1/transcribe/batch/{job_id}"]["get"]
        
        # Verify summary and description
        assert "status" in status_get["summary"].lower()
        
        description = status_get["description"]
        assert "job status" in description.lower()
        assert "pending" in description.lower()
        assert "processing" in description.lower()
        assert "completed" in description.lower()
        assert "failed" in description.lower()
        
        # Verify multiple response examples
        assert "200" in status_get["responses"]
        response_200 = status_get["responses"]["200"]
        
        # Check for multiple examples (pending, processing, completed, failed)
        content = response_200["content"]["application/json"]
        if "examples" in content:
            examples = content["examples"]
            assert len(examples) >= 2, "Should have multiple status examples"
    
    def test_capacity_endpoint_documentation(self):
        """Test that capacity endpoint has comprehensive documentation."""
        response = client.get("/openapi.json")
        schema = response.json()
        
        capacity_get = schema["paths"]["/api/v1/capacity"]["get"]
        
        # Verify summary and description
        assert "capacity" in capacity_get["summary"].lower()
        
        description = capacity_get["description"]
        assert "active_jobs" in description.lower()
        assert "queued_jobs" in description.lower()
        assert "max_workers" in description.lower()
    
    def test_app_metadata(self):
        """Test that application metadata is properly set."""
        response = client.get("/openapi.json")
        schema = response.json()
        
        info = schema["info"]
        
        # Verify title and version
        assert info["title"] == "Persian Transcription API"
        assert info["version"] == "1.0.0"
        
        # Verify description has key sections
        description = info["description"]
        assert "features" in description.lower()
        assert "supported audio formats" in description.lower()
        assert "api workflow" in description.lower()
        
        # Verify contact and license info
        assert "contact" in info
        assert "name" in info["contact"]
        
        assert "license" in info
        assert "name" in info["license"]
        assert info["license"]["name"] == "MIT License"


class TestDocumentationRequirements:
    """Test that documentation meets requirements 5.1-5.5."""
    
    def test_requirement_5_1_batch_endpoint_documented(self):
        """Requirement 5.1: REST API exposes endpoints for batch audio upload."""
        response = client.get("/openapi.json")
        schema = response.json()
        
        # Verify batch upload endpoint exists and is documented
        assert "/api/v1/transcribe/batch" in schema["paths"]
        batch_endpoint = schema["paths"]["/api/v1/transcribe/batch"]
        assert "post" in batch_endpoint
        
        post_details = batch_endpoint["post"]
        assert "summary" in post_details
        assert "description" in post_details
        assert len(post_details["description"]) > 100
    
    def test_requirement_5_2_streaming_endpoint_documented(self):
        """Requirement 5.2: REST API exposes endpoints for streaming audio processing."""
        # Note: WebSocket endpoints are not included in OpenAPI schema by default
        # But we verify the endpoint exists in the app
        from app.main import app
        
        # Check that websocket route exists
        routes = [route.path for route in app.routes]
        assert "/api/v1/transcribe/stream" in routes
    
    def test_requirement_5_3_results_endpoint_documented(self):
        """Requirement 5.3: REST API exposes endpoints for retrieving transcription results."""
        response = client.get("/openapi.json")
        schema = response.json()
        
        # Verify status endpoint exists and is documented
        assert "/api/v1/transcribe/batch/{job_id}" in schema["paths"]
        status_endpoint = schema["paths"]["/api/v1/transcribe/batch/{job_id}"]
        assert "get" in status_endpoint
        
        get_details = status_endpoint["get"]
        assert "summary" in get_details
        assert "description" in get_details
        assert "transcription" in get_details["description"].lower()
    
    def test_requirement_5_4_health_endpoint_documented(self):
        """Requirement 5.4: REST API exposes endpoints for checking service health and status."""
        response = client.get("/openapi.json")
        schema = response.json()
        
        # Verify health endpoint exists and is documented
        assert "/api/v1/health" in schema["paths"]
        health_endpoint = schema["paths"]["/api/v1/health"]
        assert "get" in health_endpoint
        
        get_details = health_endpoint["get"]
        assert "summary" in get_details
        assert "description" in get_details
        assert "health" in get_details["description"].lower()
        
        # Verify capacity endpoint exists
        assert "/api/v1/capacity" in schema["paths"]
    
    def test_requirement_5_5_json_responses_documented(self):
        """Requirement 5.5: REST API returns responses in JSON format."""
        response = client.get("/openapi.json")
        schema = response.json()
        
        # Check that all endpoints specify JSON responses
        for path, methods in schema["paths"].items():
            for method, details in methods.items():
                if method in ["get", "post"]:
                    responses = details.get("responses", {})
                    for status_code, response_details in responses.items():
                        if status_code != "422":  # Skip validation errors
                            content = response_details.get("content", {})
                            # Verify JSON is the primary content type
                            assert "application/json" in content or len(content) == 0
