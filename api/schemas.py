"""API Schemas and Request/Response Data Transfer Models.

Purpose:
    Defines Pydantic v2 data models for API requests, responses, query results,
    metrics aggregations, and typed error formats.

Inputs/Outputs:
    Inputs: Raw HTTP request bodies, database entities.
    Outputs: Validated schema instances serialized to/from JSON.

What it must NOT do:
    - Must NOT execute database queries or LLM calls.
    - Must NOT bypass Pydantic validation rules.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from generation.schema import Lesson
from shared.enums import LearnerLevel, LessonLength, RunStatus


class GenerateLessonRequest(BaseModel):
    """Payload for submitting a new lesson generation task."""
    topic: str = Field(..., max_length=300, description="Educational topic")
    learner_level: LearnerLevel = Field(default=LearnerLevel.BEGINNER, description="Audience expertise level")
    objectives: List[str] = Field(..., min_length=1, max_length=10, description="Pedagogical objectives")
    target_length: LessonLength = Field(default=LessonLength.MEDIUM, description="Target length profile")
    max_retries: int = Field(default=1, ge=0, le=2, description="Maximum retry revisions (hard cap 2)")
    reference_documents: Optional[Dict[str, str]] = Field(default=None, description="Optional source documents")


class GenerateLessonResponse(BaseModel):
    """Immediate response returned when a generation task is accepted."""
    run_id: str = Field(..., description="Unique correlation identifier for the execution")
    status: RunStatus = Field(..., description="Initial run status")
    message: str = Field(..., description="Informational message")


class RunSummaryResponse(BaseModel):
    """Compact summary of a generation run for list views."""
    id: str
    topic: str
    learner_level: str
    target_length: str
    status: str
    created_at: datetime
    updated_at: datetime
    final_lesson_id: Optional[str] = None


class RunDetailResponse(BaseModel):
    """Comprehensive details of a generation run."""
    id: str
    topic: str
    learner_level: str
    objectives: List[str]
    target_length: str
    max_retries: int
    status: str
    error_message: Optional[str] = None
    final_lesson: Optional[Lesson] = None
    evaluations: List[Dict[str, Any]] = Field(default_factory=list)
    rejection_logs: List[Dict[str, Any]] = Field(default_factory=list)
    tokens: List[Dict[str, Any]] = Field(default_factory=list)
    self_judged: bool = True
    not_externally_verified: bool = True
    hint_version: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class LessonVersionResponse(BaseModel):
    """Snapshot of an individual lesson version iteration."""
    id: str
    version_number: int
    content: Dict[str, Any]
    changes_made: List[str]
    created_at: datetime
    evaluations: List[Dict[str, Any]] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    """User feedback submitted for a generated lesson."""
    rating: int = Field(..., ge=1, le=5, description="1 to 5 star rating")
    issue_tags: List[str] = Field(default_factory=list, description="Categorical tags for issues")
    comment: Optional[str] = Field(default=None, description="Free-form user critique")


class MetricsResponse(BaseModel):
    """System-wide performance, quality, and token efficiency metrics."""
    total_runs: int
    first_attempt_pass_rate: float
    overall_pass_rate: float
    retry_distribution: Dict[str, int]
    avg_tokens_per_run: float
    top_failing_criteria: List[Dict[str, Any]]
    pass_rate_with_hint: Optional[float] = None
    pass_rate_without_hint: Optional[float] = None


class ErrorResponse(BaseModel):
    """Standardized typed error response schema."""
    detail: str
    error_type: str
    correlation_id: Optional[str] = None
