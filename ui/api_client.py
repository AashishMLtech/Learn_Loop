"""UI API Client Module.

Purpose:
    Provides an HTTP client abstraction for the NiceGUI frontend to communicate
    with the FastAPI backend over HTTP, supporting generation dispatch, run status
    polling, cancellation, feedback submission, metrics retrieval, and health checks.

Inputs/Outputs:
    Inputs: Frontend action payloads and query identifiers.
    Outputs: Deserialized JSON data transfer dictionaries or ApiClientError.

What it must NOT do:
    - Must NOT execute generation, evaluation, or database queries directly.
    - Must NOT import backend database or LLM services.
"""
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("lesson_generator.ui.client")


class ApiClientError(Exception):
    """Raised when an API request fails due to network outage or non-200 HTTP response."""
    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ApiClient:
    """HTTP Client communicating with the backend FastAPI service."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 15.0,
    ) -> None:
        """Initializes the ApiClient.

        Args:
            base_url: Base URL of the FastAPI server. Defaults to env API_URL or http://127.0.0.1:8000.
            api_key: Static API key. Defaults to env API_KEY or default-insecure-api-key.
            timeout: Request timeout in seconds.
        """
        self.base_url = (base_url or os.getenv("API_URL", "http://127.0.0.1:8000")).rstrip("/")
        self.api_key = api_key or os.getenv("API_KEY", "default-insecure-api-key")
        self.timeout = timeout

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def check_health(self) -> bool:
        """Checks API liveness.

        Returns:
            True if healthy, False otherwise.
        """
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(f"{self.base_url}/health")
                return res.status_code == 200
        except Exception as exc:
            logger.debug("Health check failed: %s", exc)
            return False

    def check_ready(self) -> Dict[str, Any]:
        """Checks backend readiness probe.

        Returns:
            Readiness status dictionary.

        Raises:
            ApiClientError: If probe is unreachable.
        """
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(f"{self.base_url}/ready")
                return res.json()
        except Exception as exc:
            raise ApiClientError(f"Ready probe unreachable: {exc}") from exc

    def generate_lesson(
        self,
        topic: str,
        learner_level: str,
        objectives: List[str],
        target_length: str,
        max_retries: int = 1,
        reference_documents: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Submits a new lesson generation request.

        Args:
            topic: Educational subject.
            learner_level: Learner proficiency level.
            objectives: Pedagogical goals.
            target_length: Content length profile.
            max_retries: Retry revision cap (0 to 2).
            reference_documents: Optional reference documents.

        Returns:
            Dictionary containing run_id and status.

        Raises:
            ApiClientError: On HTTP error or connection failure.
        """
        url = f"{self.base_url}/api/v1/lessons/generate"
        payload = {
            "topic": topic,
            "learner_level": learner_level,
            "objectives": objectives,
            "target_length": target_length,
            "max_retries": max_retries,
            "reference_documents": reference_documents,
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(url, json=payload, headers=self._headers)
                if res.status_code == 429:
                    raise ApiClientError("Rate limit exceeded. Please wait a moment.", 429)
                if not res.is_success:
                    err_detail = res.text
                    try:
                        err_detail = res.json().get("detail", err_detail)
                    except Exception:
                        pass
                    raise ApiClientError(f"Generation request failed ({res.status_code}): {err_detail}", res.status_code)
                return res.json()
        except httpx.HTTPError as exc:
            raise ApiClientError(f"Network error contacting API: {exc}") from exc

    def get_runs(self) -> List[Dict[str, Any]]:
        """Fetches all past lesson runs.

        Returns:
            List of run summary dictionaries.

        Raises:
            ApiClientError: On HTTP error.
        """
        url = f"{self.base_url}/api/v1/runs"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(url, headers=self._headers)
                if not res.is_success:
                    raise ApiClientError(f"Failed to fetch runs ({res.status_code}): {res.text}", res.status_code)
                return res.json()
        except httpx.HTTPError as exc:
            raise ApiClientError(f"Network error: {exc}") from exc

    def get_run(self, run_id: str) -> Dict[str, Any]:
        """Fetches details for a single run.

        Args:
            run_id: Run identifier.

        Returns:
            Run detail dictionary.

        Raises:
            ApiClientError: On HTTP error or 404.
        """
        url = f"{self.base_url}/api/v1/runs/{run_id}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(url, headers=self._headers)
                if res.status_code == 404:
                    raise ApiClientError(f"Run {run_id} not found.", 404)
                if not res.is_success:
                    raise ApiClientError(f"Failed to load run ({res.status_code}): {res.text}", res.status_code)
                return res.json()
        except httpx.HTTPError as exc:
            raise ApiClientError(f"Network error: {exc}") from exc

    def get_history(self, run_id: str) -> List[Dict[str, Any]]:
        """Fetches iteration version history for a run.

        Args:
            run_id: Run identifier.

        Returns:
            List of version snapshot dictionaries.

        Raises:
            ApiClientError: On HTTP error.
        """
        url = f"{self.base_url}/api/v1/runs/{run_id}/history"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(url, headers=self._headers)
                if not res.is_success:
                    raise ApiClientError(f"Failed to fetch history ({res.status_code}): {res.text}", res.status_code)
                return res.json()
        except httpx.HTTPError as exc:
            raise ApiClientError(f"Network error: {exc}") from exc

    def cancel_run(self, run_id: str) -> Dict[str, Any]:
        """Requests cancellation of a running task.

        Args:
            run_id: Run identifier.

        Returns:
            Response dictionary.

        Raises:
            ApiClientError: On HTTP error.
        """
        url = f"{self.base_url}/api/v1/runs/{run_id}/cancel"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(url, headers=self._headers)
                if not res.is_success:
                    raise ApiClientError(f"Failed to cancel run ({res.status_code}): {res.text}", res.status_code)
                return res.json()
        except httpx.HTTPError as exc:
            raise ApiClientError(f"Network error: {exc}") from exc

    def submit_feedback(
        self,
        run_id: str,
        rating: int,
        issue_tags: Optional[List[str]] = None,
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submits user satisfaction evaluation and critique.

        Args:
            run_id: Run identifier.
            rating: Rating between 1 and 5.
            issue_tags: Categorical tags.
            comment: Optional text commentary.

        Returns:
            Response dictionary.

        Raises:
            ApiClientError: On HTTP error.
        """
        url = f"{self.base_url}/api/v1/runs/{run_id}/feedback"
        payload = {
            "rating": rating,
            "issue_tags": issue_tags or [],
            "comment": comment,
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(url, json=payload, headers=self._headers)
                if not res.is_success:
                    raise ApiClientError(f"Failed to submit feedback ({res.status_code}): {res.text}", res.status_code)
                return res.json()
        except httpx.HTTPError as exc:
            raise ApiClientError(f"Network error: {exc}") from exc

    def get_metrics(self) -> Dict[str, Any]:
        """Retrieves global system metrics.

        Returns:
            Metrics dictionary.

        Raises:
            ApiClientError: On HTTP error.
        """
        url = f"{self.base_url}/api/v1/metrics"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(url, headers=self._headers)
                if not res.is_success:
                    raise ApiClientError(f"Failed to fetch metrics ({res.status_code}): {res.text}", res.status_code)
                return res.json()
        except httpx.HTTPError as exc:
            raise ApiClientError(f"Network error: {exc}") from exc

    def get_rubric(self) -> Dict[str, Any]:
        """Retrieves active evaluation rubric specification.

        Returns:
            Rubric dictionary.

        Raises:
            ApiClientError: On HTTP error.
        """
        url = f"{self.base_url}/api/v1/config/rubric"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(url, headers=self._headers)
                if not res.is_success:
                    raise ApiClientError(f"Failed to fetch rubric ({res.status_code}): {res.text}", res.status_code)
                return res.json()
        except httpx.HTTPError as exc:
            raise ApiClientError(f"Network error: {exc}") from exc
