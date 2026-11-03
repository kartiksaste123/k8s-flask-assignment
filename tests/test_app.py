"""Unit tests for the Flask endpoints (run with: pytest -v)."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest  # noqa: E402

from app import app  # noqa: E402


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_home_page(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Served by pod / container" in resp.data
    assert b"Version" in resp.data


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "healthy"
    assert "pod_name" in data


def test_api_info(client):
    resp = client.get("/api/info")
    assert resp.status_code == 200
    data = resp.get_json()
    for key in ("app_name", "version", "pod_name", "hostname", "server_time_utc"):
        assert key in data


def test_pod_name_from_env(client, monkeypatch):
    monkeypatch.setenv("POD_NAME", "test-pod-123")
    assert client.get("/api/info").get_json()["pod_name"] == "test-pod-123"


def test_404_returns_json(client):
    resp = client.get("/does-not-exist")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "not found"
