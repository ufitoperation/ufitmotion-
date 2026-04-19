"""
test_health.py — Tests for the /api/health endpoint.

Verifies:
  1. The endpoint responds with HTTP 200.
  2. The response body contains { ok: true }.
  3. The response body contains the 'env' field.
"""

import json


def test_health_returns_200(client):
    """GET /api/health should return HTTP 200 OK."""
    response = client.get("/api/health")
    assert response.status_code == 200


def test_health_returns_ok_true(client):
    """GET /api/health response body should contain { ok: true }."""
    response = client.get("/api/health")
    data = json.loads(response.data)
    assert data.get("ok") is True


def test_health_returns_env_field(client):
    """GET /api/health response body should contain an 'env' field."""
    response = client.get("/api/health")
    data = json.loads(response.data)
    assert "env" in data
    # In the test configuration, APP_ENV is set to "test".
    assert isinstance(data["env"], str)
    assert len(data["env"]) > 0
