"""
Tests for CORS security configuration.
"""
from fastapi.testclient import TestClient
from app.main import app
from app.config import CORS_ALLOWED_ORIGINS

def test_cors_allowed_origin():
    client = TestClient(app)
    if CORS_ALLOWED_ORIGINS:
        allowed_origin = CORS_ALLOWED_ORIGINS[0]
        response = client.options("/api/status", headers={
            "Origin": allowed_origin,
            "Access-Control-Request-Method": "GET"
        })
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == allowed_origin
    else:
        # Should not happen with default config
        pass

def test_cors_disallowed_origin():
    client = TestClient(app)
    disallowed_origin = "http://malicious-site.com"
    response = client.options("/api/status", headers={
        "Origin": disallowed_origin,
        "Access-Control-Request-Method": "GET"
    })
    # CORSMiddleware returns 400 if origin is not allowed for preflight
    assert response.status_code == 400
    assert response.headers.get("access-control-allow-origin") is None
