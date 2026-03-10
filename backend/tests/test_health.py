"""Tests for the health endpoint."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_ollama_reachable():
    """Health endpoint returns 'reachable' when Ollama responds 200."""
    mock_response = httpx.Response(200, json={"models": []})

    with patch("main.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resp = client.get("/api/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["ollama"] == "reachable"


def test_health_ollama_unreachable():
    """Health endpoint returns 503 when Ollama is down (readiness check)."""
    with patch("main.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resp = client.get("/api/health")

    assert resp.status_code == 503
    data = resp.json()
    assert data["status"] == "degraded"
    assert data["ollama"] == "unreachable"
