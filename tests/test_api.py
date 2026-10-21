"""Integration Tests for FastAPI Endpoints.

Purpose:
    Tests HTTP endpoints: generation dispatch, status polling, version history,
    run cancellation, user feedback recording, metric calculations, rubric queries,
    rate limiting enforcement (429), and API key authentication (401).

Inputs/Outputs:
    Inputs: Mock HTTP requests using TestClient.
    Outputs: Assertions on status codes, JSON response schemas, and database updates.

What it must NOT do:
    - Must NOT hardcode demo topic terms.
    - Must NOT make external network requests to model providers.
"""
import uuid
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.config import settings
from api.main import app
from api.routes import _rate_limit_records
from memory.store import RunModel, get_db_context, init_db
from shared.enums import RunStatus

client = TestClient(app)
VALID_HEADERS = {"X-API-Key": settings.api_key}


def setup_module() -> None:
    """Initializes database schema before running endpoint tests."""
    init_db()


def test_health_and_ready_endpoints() -> None:
    """Verifies public liveness and readiness probe endpoints."""
    # /health
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json() == {"status": "ok"}

    # /ready
    res_ready = client.get("/ready")
    assert res_ready.status_code == 200
    data = res_ready.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"


def test_authentication_enforcement() -> None:
    """Verifies that protected API endpoints reject missing or invalid API keys."""
    # Missing header -> 401
    res_missing = client.get("/api/v1/runs")
    assert res_missing.status_code == 401

    # Invalid header -> 401
    res_invalid = client.get("/api/v1/runs", headers={"X-API-Key": "wrong-secret-token"})
    assert res_invalid.status_code == 401

    # Valid header -> 200
    res_valid = client.get("/api/v1/runs", headers=VALID_HEADERS)
    assert res_valid.status_code == 200


@patch("api.routes.background_run_pipeline")
def test_generate_lesson_endpoint(mock_background: Any) -> None:
    """Verifies valid lesson generation submission and parameter validation."""
    payload = {
        "topic": "Binary Search Trees",
        "learner_level": "beginner",
        "objectives": ["Understand node insertion", "Learn search traversal"],
        "target_length": "short",
        "max_retries": 1,
    }

    response = client.post("/api/v1/lessons/generate", json=payload, headers=VALID_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    assert data["status"] == "RUNNING"
    mock_background.assert_called_once()

    # Invalid payload (empty topic) -> 422
    invalid_payload = {
        "topic": "   ",
        "learner_level": "beginner",
        "objectives": ["Empty topic test"],
        "target_length": "short",
    }
    res_inv = client.post("/api/v1/lessons/generate", json=invalid_payload, headers=VALID_HEADERS)
    assert res_inv.status_code == 422


def test_rate_limiting_enforcement() -> None:
    """Verifies that exceeding per-minute request rate returns 429 Too Many Requests."""
    _rate_limit_records.clear()
    original_rate = settings.rate_limit_per_minute
    settings.rate_limit_per_minute = 2

    try:
        payload = {
            "topic": "Rate Limit Topic",
            "learner_level": "beginner",
            "objectives": ["Rate limit test"],
            "target_length": "short",
        }
        with patch("api.routes.background_run_pipeline"):
            # First request
            res1 = client.post("/api/v1/lessons/generate", json=payload, headers=VALID_HEADERS)
            assert res1.status_code == 200

            # Second request
            res2 = client.post("/api/v1/lessons/generate", json=payload, headers=VALID_HEADERS)
            assert res2.status_code == 200

            # Third request should hit rate limit (ceiling is 2)
            res3 = client.post("/api/v1/lessons/generate", json=payload, headers=VALID_HEADERS)
            assert res3.status_code == 429
            assert "Rate limit exceeded" in res3.json()["detail"]
    finally:
        settings.rate_limit_per_minute = original_rate


def test_run_detail_history_cancel_and_feedback() -> None:
    """Verifies run lifecycle endpoints: details, history, cancellation, and feedback."""
    # Seed a test run
    test_run_id = f"test-endpoint-run-{uuid.uuid4()}"
    with get_db_context() as db:
        db.add(
            RunModel(
                id=test_run_id,
                topic="Graph Data Structures",
                learner_level="beginner",
                objectives=["Adjacency list representation"],
                target_length="medium",
                status=RunStatus.RUNNING.value,
            )
        )

    # 1. GET /runs/{id}
    res_detail = client.get(f"/api/v1/runs/{test_run_id}", headers=VALID_HEADERS)
    assert res_detail.status_code == 200
    assert res_detail.json()["topic"] == "Graph Data Structures"

    # 2. GET /runs/{id}/history
    res_hist = client.get(f"/api/v1/runs/{test_run_id}/history", headers=VALID_HEADERS)
    assert res_hist.status_code == 200
    assert isinstance(res_hist.json(), list)

    # 3. POST /runs/{id}/cancel
    res_cancel = client.get(f"/api/v1/runs/{test_run_id}", headers=VALID_HEADERS)
    assert res_cancel.json()["status"] == "RUNNING"

    res_post_cancel = client.post(f"/api/v1/runs/{test_run_id}/cancel", headers=VALID_HEADERS)
    assert res_post_cancel.status_code == 200
    assert res_post_cancel.json()["status"] == "CANCELLED"

    # 4. POST /runs/{id}/feedback
    fb_payload = {
        "rating": 5,
        "issue_tags": ["clear_walkthrough"],
        "comment": "Very informative breakdown.",
    }
    res_fb = client.post(f"/api/v1/runs/{test_run_id}/feedback", json=fb_payload, headers=VALID_HEADERS)
    assert res_fb.status_code == 200
    assert res_fb.json()["status"] == "ok"


def test_metrics_and_rubric_endpoints() -> None:
    """Verifies metrics aggregation and rubric configuration query endpoints."""
    # GET /metrics
    res_metrics = client.get("/api/v1/metrics", headers=VALID_HEADERS)
    assert res_metrics.status_code == 200
    metrics_data = res_metrics.json()
    assert "total_runs" in metrics_data
    assert "overall_pass_rate" in metrics_data
    assert "avg_tokens_per_run" in metrics_data

    # GET /config/rubric
    res_rubric = client.get("/api/v1/config/rubric", headers=VALID_HEADERS)
    assert res_rubric.status_code == 200
    rubric_data = res_rubric.json()
    assert "version" in rubric_data
    assert "criteria" in rubric_data
