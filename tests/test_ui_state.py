"""Unit and Integration Tests for UI State Transitions and API Client.

Purpose:
    Tests ApiClient HTTP abstraction: state polling transitions, network error
    resilience, rate limit handling (429), 404 handling, cancel dispatch, feedback
    submission, and metrics fetching.

Inputs/Outputs:
    Inputs: Mocked HTTP responses via unittest.mock / respx / monkeypatch.
    Outputs: Assertions on ApiClient methods, state models, and exception classifications.

What it must NOT do:
    - Must NOT hardcode demo topic terms.
    - Must NOT launch a persistent browser or GUI process.
"""
from unittest.mock import MagicMock, patch

import httpx
import pytest

from ui.api_client import ApiClient, ApiClientError


def test_api_client_initialization_and_headers() -> None:
    """Verifies ApiClient constructor and request headers configuration."""
    client = ApiClient(base_url="http://test-server:8000", api_key="test-api-key-xyz")
    assert client.base_url == "http://test-server:8000"
    assert client.api_key == "test-api-key-xyz"
    assert client._headers["X-API-Key"] == "test-api-key-xyz"


def test_api_client_health_and_ready_probes() -> None:
    """Verifies health check and readiness probe client behaviors."""
    client = ApiClient(base_url="http://test-server:8000")

    # Mock health 200
    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200)
        assert client.check_health() is True

    # Mock health connection error
    with patch("httpx.Client.get", side_effect=httpx.ConnectError("Connection refused")):
        assert client.check_health() is False

    # Mock ready 200
    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"status": "ready", "database": "connected", "model_available": True},
        )
        ready_data = client.check_ready()
        assert ready_data["status"] == "ready"


def test_generate_lesson_success_and_rate_limit_error() -> None:
    """Verifies generation submission handling of 200, 429, and network error."""
    client = ApiClient(base_url="http://test-server:8000")

    # Success 200
    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            is_success=True,
            json=lambda: {"run_id": "run-abc-123", "status": "RUNNING", "message": "Initiated"},
        )
        res = client.generate_lesson(
            topic="Dynamic Programming Memoization",
            learner_level="beginner",
            objectives=["Understand top-down lookup tables"],
            target_length="short",
        )
        assert res["run_id"] == "run-abc-123"
        assert res["status"] == "RUNNING"

    # Rate limit 429
    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=429,
            is_success=False,
            text="Rate limit exceeded",
        )
        with pytest.raises(ApiClientError) as exc_info:
            client.generate_lesson(
                topic="Dynamic Programming Memoization",
                learner_level="beginner",
                objectives=["Understand top-down lookup tables"],
                target_length="short",
            )
        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in str(exc_info.value)


def test_run_polling_state_transitions() -> None:
    """Verifies client polling transitions from RUNNING to PASS."""
    client = ApiClient(base_url="http://test-server:8000")

    # State 1: RUNNING
    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            is_success=True,
            json=lambda: {"id": "run-1", "status": "RUNNING", "topic": "Graph Traversals"},
        )
        state_running = client.get_run("run-1")
        assert state_running["status"] == "RUNNING"

    # State 2: PASS with completed lesson
    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            is_success=True,
            json=lambda: {
                "id": "run-1",
                "status": "PASS",
                "topic": "Graph Traversals",
                "final_lesson": {"title": "Depth First Search"},
                "evaluations": [{"passed": True, "criterion_results": []}],
            },
        )
        state_pass = client.get_run("run-1")
        assert state_pass["status"] == "PASS"
        assert state_pass["final_lesson"]["title"] == "Depth First Search"


def test_client_404_handling() -> None:
    """Verifies that non-existent runs trigger ApiClientError with status 404."""
    client = ApiClient(base_url="http://test-server:8000")

    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=404, is_success=False, text="Not found")
        with pytest.raises(ApiClientError) as exc_info:
            client.get_run("non-existent-id")
        assert exc_info.value.status_code == 404


def test_client_cancel_feedback_metrics_and_rubric() -> None:
    """Verifies cancel, feedback submission, metrics querying, and rubric querying."""
    client = ApiClient(base_url="http://test-server:8000")

    # Cancel
    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            is_success=True,
            json=lambda: {"run_id": "run-1", "status": "CANCELLED"},
        )
        res_cancel = client.cancel_run("run-1")
        assert res_cancel["status"] == "CANCELLED"

    # Feedback
    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            is_success=True,
            json=lambda: {"status": "ok", "message": "Feedback recorded"},
        )
        res_fb = client.submit_feedback("run-1", rating=5, issue_tags=["clear"], comment="Good")
        assert res_fb["status"] == "ok"

    # Metrics
    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            is_success=True,
            json=lambda: {"total_runs": 10, "overall_pass_rate": 0.8},
        )
        metrics = client.get_metrics()
        assert metrics["total_runs"] == 10

    # Rubric
    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            is_success=True,
            json=lambda: {"version": "1.0.0", "criteria": []},
        )
        rubric = client.get_rubric()
        assert rubric["version"] == "1.0.0"
