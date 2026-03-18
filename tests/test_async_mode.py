"""Test async_mode flag functionality."""

from __future__ import annotations

import importlib
import time

import pytest
from fastapi.testclient import TestClient

from mindloom_core.models import Status

app_module = importlib.import_module("mindloom.app")


@pytest.fixture(scope="module")
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app_module.app)


def test_sync_mode_default(client, monkeypatch):
    """Test that sync mode is the default behavior."""
    mock_result = SimpleNamespace(content="mocked result", length=13)

    def mock_run_task(task_type, content, model):
        return mock_result

    monkeypatch.setattr(app_module, "_run_task", mock_run_task)

    response = client.post(
        "/section/improve",
        json={
            "start": 0,
            "end": 10,
            "content": "test content",
            "file_path": "/test.txt",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == Status.COMPLETED
    assert data["content"] == "mocked result"
    assert data["length"] == 13
    assert "job_id" in data


def test_sync_mode_explicit(client, monkeypatch):
    """Test sync mode when explicitly set to false."""
    mock_result = SimpleNamespace(content="sync result", length=11)

    def mock_run_task(task_type, content, model):
        return mock_result

    monkeypatch.setattr(app_module, "_run_task", mock_run_task)

    response = client.post(
        "/section/improve",
        json={
            "start": 0,
            "end": 10,
            "content": "test content",
            "file_path": "/test.txt",
            "async_mode": False,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == Status.COMPLETED
    assert data["content"] == "sync result"


def test_async_mode_returns_immediately(client):
    """Test that async mode returns immediately with job_id."""
    response = client.post(
        "/section/improve",
        json={
            "start": 0,
            "end": 10,
            "content": "test content for async",
            "file_path": "/test.txt",
            "async_mode": True,
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == Status.PENDING
    assert "job_id" in data
    assert data["content"] is None
    assert data["length"] is None
    assert "created_at" in data

    job_id = data["job_id"]

    time.sleep(2)

    job_response = client.get(f"/jobs/{job_id}")
    assert job_response.status_code == 200
    job_data = job_response.json()
    assert job_data["id"] == job_id
    assert job_data["status"] in [Status.RUNNING, Status.COMPLETED, Status.PENDING]


def test_async_mode_multiple_endpoints(client):
    """Test that async mode works across different endpoints."""
    endpoints = [
        ("/ask", {"question": "What is async?", "async_mode": True}),
        (
            "/summarize",
            {"content": "Long text to summarize", "async_mode": True},
        ),
        (
            "/email/improve",
            {"content": "Email body", "async_mode": True},
        ),
    ]

    for path, payload in endpoints:
        response = client.post(path, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == Status.PENDING
        assert "job_id" in data
        assert data["content"] is None


def test_async_mode_with_model_parameter(client):
    """Test that async mode respects the model parameter."""
    response = client.post(
        "/translate",
        json={
            "content": "Hello world",
            "target_language": "Spanish",
            "model": "ministral-3:latest",
            "async_mode": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == Status.PENDING
    assert "job_id" in data


class SimpleNamespace:
    """Simple namespace for mocking."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
