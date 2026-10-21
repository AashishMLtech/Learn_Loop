"""API Endpoints and Route Handlers Module.

Purpose:
    Provides HTTP REST endpoints for lesson generation dispatch, run inspection,
    cancellation, user feedback submission, metric aggregation, rubric queries,
    and health/readiness probes.

Inputs/Outputs:
    Inputs: HTTP requests with X-API-Key header and JSON bodies.
    Outputs: JSON responses matching schemas defined in api/schemas.py.

What it must NOT do:
    - Must NOT perform synchronous blocking LLM calls inside HTTP request threads.
    - Must NOT bypass API key authentication on protected endpoints.
    - Must NOT allow rate limit violations.
"""
import asyncio
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from sqlalchemy import select, text

from agent.graph import create_lesson_graph
from api.config import settings
from api.schemas import (
    FeedbackRequest,
    GenerateLessonRequest,
    GenerateLessonResponse,
    LessonVersionResponse,
    MetricsResponse,
    RunDetailResponse,
    RunSummaryResponse,
)
from evaluation.judge import JudgeService
from generation.schema import Lesson
from generation.service import GeneratorService
from guardrails.input import InputValidationError, validate_generation_request
from memory.store import (
    FeedbackModel,
    LessonVersionModel,
    RejectionLogModel,
    RunModel,
    TokenUsageModel,
    get_common_pitfalls_hint,
    get_db_context,
)
from shared.enums import EvidenceMode, RunStatus
from shared.llm_client import GroqLLMClient, TokenBudgetTracker

logger = logging.getLogger("lesson_generator.api.routes")
router = APIRouter()

# In-memory sliding window rate limiter: {api_key: [timestamp1, timestamp2, ...]}
_rate_limit_lock = asyncio.Lock()
_rate_limit_records: Dict[str, List[float]] = {}


def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> str:
    """Authenticates static single-tenant API Key from request headers.

    Args:
        x_api_key: Header value provided in request.

    Returns:
        The validated API key string.

    Raises:
        HTTPException: 401 Unauthorized if missing or incorrect.
    """
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Provide header 'X-API-Key'.",
        )
    return x_api_key


async def enforce_rate_limit(api_key: str = Depends(verify_api_key)) -> None:
    """Enforces per-key sliding window rate limits on generation requests.

    Args:
        api_key: Authenticated API key.

    Raises:
        HTTPException: 429 Too Many Requests if rate ceiling is exceeded.
    """
    now = time.time()
    window = 60.0
    async with _rate_limit_lock:
        timestamps = _rate_limit_records.get(api_key, [])
        valid_timestamps = [t for t in timestamps if now - t < window]
        if len(valid_timestamps) >= settings.rate_limit_per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {settings.rate_limit_per_minute} requests per minute.",
            )
        valid_timestamps.append(now)
        _rate_limit_records[api_key] = valid_timestamps


def background_run_pipeline(
    run_id: str,
    topic: str,
    learner_level: str,
    objectives: List[str],
    target_length: str,
    max_retries: int,
    reference_documents: Optional[Dict[str, str]] = None,
) -> None:
    """Executes the lesson generation state graph asynchronously in background.

    Args:
        run_id: Run identifier.
        topic: Educational subject.
        learner_level: Audience skill level.
        objectives: Pedagogical goals.
        target_length: Content length profile.
        max_retries: Retry revision cap.
        reference_documents: Optional source documents.
    """
    logger.info("Starting background execution for run %s", run_id)
    api_key = os.getenv("GROQ_API_KEY")
    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    llm_client = GroqLLMClient(api_key=api_key, model=model)
    gen_service = GeneratorService(llm_client, model=model)
    judge_service = JudgeService(llm_client, model=model)
    token_tracker = TokenBudgetTracker()

    with get_db_context() as db:
        hint_text, hint_ver = get_common_pitfalls_hint(db)

    supplied_sources: List[Dict[str, str]] = []
    ref_context = ""
    evidence_mode = EvidenceMode.MODEL_KNOWLEDGE_ONLY
    if reference_documents:
        evidence_mode = EvidenceMode.PROVIDED_DOCS
        for s_id, s_text in reference_documents.items():
            supplied_sources.append({"source_id": s_id, "title": s_id})
            ref_context += f"\n--- Source {s_id} ---\n{s_text}\n"

    initial_state = {
        "run_id": run_id,
        "topic": topic,
        "learner_level": learner_level,
        "learning_objectives": objectives,
        "target_length": target_length,
        "max_retries": max_retries,
        "supplied_sources": supplied_sources,
        "reference_context": ref_context,
        "evidence_mode": evidence_mode,
        "pitfall_hints": hint_text,
        "hint_version": hint_ver,
        "services": {
            "generator_service": gen_service,
            "judge_service": judge_service,
        },
        "token_tracker": token_tracker,
    }

    graph = create_lesson_graph()
    try:
        graph.invoke(initial_state)
    except Exception as exc:
        logger.error("Background run %s crashed: %s", run_id, exc, exc_info=True)
        with get_db_context() as db:
            run = db.get(RunModel, run_id)
            if run and run.status == RunStatus.RUNNING.value:
                run.status = RunStatus.ERROR.value
                run.error_message = f"Runtime pipeline exception: {exc}"


# ==========================================
# Core API Routes
# ==========================================

@router.post("/lessons/generate", response_model=GenerateLessonResponse, dependencies=[Depends(enforce_rate_limit)])
def generate_lesson_endpoint(
    req: GenerateLessonRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key),
) -> GenerateLessonResponse:
    """Dispatches a new lesson generation task to run in the background.

    Args:
        req: Validated generation request payload.
        background_tasks: FastAPI background worker task queue.
        api_key: Authenticated API key.

    Returns:
        GenerateLessonResponse containing run_id and initial status.

    Raises:
        HTTPException: 422 if inputs fail validation.
    """
    try:
        validated = validate_generation_request(
            topic=req.topic,
            learner_level=req.learner_level,
            objectives=req.objectives,
            target_length=req.target_length,
            max_retries=req.max_retries,
        )
    except InputValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    run_id = str(uuid.uuid4())

    with get_db_context() as db:
        run = RunModel(
            id=run_id,
            topic=validated["topic"],
            learner_level=validated["learner_level"].value,
            objectives=validated["objectives"],
            target_length=validated["target_length"].value,
            max_retries=validated["max_retries"],
            status=RunStatus.RUNNING.value,
        )
        db.add(run)

    background_tasks.add_task(
        background_run_pipeline,
        run_id=run_id,
        topic=validated["topic"],
        learner_level=validated["learner_level"],
        objectives=validated["objectives"],
        target_length=validated["target_length"],
        max_retries=validated["max_retries"],
        reference_documents=req.reference_documents,
    )

    return GenerateLessonResponse(
        run_id=run_id,
        status=RunStatus.RUNNING,
        message="Lesson generation initiated in background worker.",
    )


@router.get("/runs", response_model=List[RunSummaryResponse], dependencies=[Depends(verify_api_key)])
def list_runs_endpoint() -> List[RunSummaryResponse]:
    """Retrieves summaries of all generation runs ordered by newest first."""
    with get_db_context() as db:
        stmt = select(RunModel).order_by(RunModel.created_at.desc())
        runs = list(db.scalars(stmt).all())
        return [
            RunSummaryResponse(
                id=r.id,
                topic=r.topic,
                learner_level=r.learner_level,
                target_length=r.target_length,
                status=r.status,
                created_at=r.created_at,
                updated_at=r.updated_at,
                final_lesson_id=r.final_lesson_id,
            )
            for r in runs
        ]


@router.get("/runs/{run_id}", response_model=RunDetailResponse, dependencies=[Depends(verify_api_key)])
def get_run_detail_endpoint(run_id: str) -> RunDetailResponse:
    """Retrieves comprehensive details, evaluations, rejection log, and lesson content for a run.

    Args:
        run_id: Unique run identifier.

    Returns:
        RunDetailResponse containing run state and evaluations.

    Raises:
        HTTPException: 404 if run not found.
    """
    with get_db_context() as db:
        run = db.get(RunModel, run_id)
        if not run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")

        final_lesson = None
        if run.final_lesson_id:
            version_record = db.get(LessonVersionModel, run.final_lesson_id)
            if version_record and version_record.content:
                try:
                    final_lesson = Lesson.model_validate(version_record.content)
                except Exception as exc:
                    logger.warning("Could not parse final lesson content: %s", exc)

        evaluations_data = [
            {
                "id": e.id,
                "lesson_version_id": e.lesson_version_id,
                "rubric_version": e.rubric_version,
                "judge_model": e.judge_model,
                "criterion_results": e.criterion_results,
                "claims": e.claims,
                "passed": e.passed,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in run.evaluations
        ]

        rejection_data = [
            {
                "attempt": r.attempt,
                "failed_criteria": r.failed_criteria,
                "reasons": r.reasons,
                "changes_made": r.changes_made,
                "result": r.result,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in run.rejection_logs
        ]

        token_data = [
            {
                "attempt": t.attempt,
                "call_type": t.call_type,
                "model": t.model,
                "prompt_tokens": t.prompt_tokens,
                "completion_tokens": t.completion_tokens,
                "total_tokens": t.total_tokens,
            }
            for t in run.tokens
        ]

        return RunDetailResponse(
            id=run.id,
            topic=run.topic,
            learner_level=run.learner_level,
            objectives=run.objectives,
            target_length=run.target_length,
            max_retries=run.max_retries,
            status=run.status,
            error_message=run.error_message,
            final_lesson=final_lesson,
            evaluations=evaluations_data,
            rejection_logs=rejection_data,
            tokens=token_data,
            self_judged=run.self_judged,
            not_externally_verified=run.not_externally_verified,
            hint_version=run.hint_version,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )


@router.get("/runs/{run_id}/history", response_model=List[LessonVersionResponse], dependencies=[Depends(verify_api_key)])
def get_run_history_endpoint(run_id: str) -> List[LessonVersionResponse]:
    """Retrieves complete version history and evaluations for an individual run.

    Args:
        run_id: Unique run identifier.

    Returns:
        List of LessonVersionResponse models.

    Raises:
        HTTPException: 404 if run not found.
    """
    with get_db_context() as db:
        run = db.get(RunModel, run_id)
        if not run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")

        result = []
        for v in run.versions:
            evals = [
                {
                    "rubric_version": e.rubric_version,
                    "passed": e.passed,
                    "criterion_results": e.criterion_results,
                }
                for e in v.evaluations
            ]
            result.append(
                LessonVersionResponse(
                    id=v.id,
                    version_number=v.version_number,
                    content=v.content,
                    changes_made=v.changes_made,
                    created_at=v.created_at,
                    evaluations=evals,
                )
            )
        return result


@router.post("/runs/{run_id}/cancel", dependencies=[Depends(verify_api_key)])
def cancel_run_endpoint(run_id: str) -> Dict[str, Any]:
    """Signals cancellation to an active run.

    Args:
        run_id: Unique run identifier.

    Returns:
        Cancellation status dictionary.

    Raises:
        HTTPException: 404 if run not found.
    """
    with get_db_context() as db:
        run = db.get(RunModel, run_id)
        if not run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")

        run.cancel_requested = True
        if run.status == RunStatus.RUNNING.value:
            run.status = RunStatus.CANCELLED.value
            run.error_message = "Cancelled by user request."

        return {"run_id": run_id, "status": run.status, "message": "Cancellation request registered."}


@router.post("/runs/{run_id}/feedback", dependencies=[Depends(verify_api_key)])
def submit_feedback_endpoint(run_id: str, feedback: FeedbackRequest) -> Dict[str, str]:
    """Accepts user satisfaction ratings and feedback tags for a finished lesson.

    Args:
        run_id: Unique run identifier.
        feedback: FeedbackRequest payload with rating, tags, and comment.

    Returns:
        Status acknowledgement dictionary.

    Raises:
        HTTPException: 404 if run not found.
    """
    with get_db_context() as db:
        run = db.get(RunModel, run_id)
        if not run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")

        fb = FeedbackModel(
            run_id=run_id,
            rating=feedback.rating,
            issue_tags=feedback.issue_tags,
            comment=feedback.comment,
        )
        db.add(fb)

    return {"status": "ok", "message": "User feedback recorded successfully."}


@router.get("/metrics", response_model=MetricsResponse, dependencies=[Depends(verify_api_key)])
def get_metrics_endpoint() -> MetricsResponse:
    """Calculates operational and quality metrics across all historical runs."""
    with get_db_context() as db:
        all_runs = list(db.scalars(select(RunModel)).all())
        total_runs = len(all_runs)

        if total_runs == 0:
            return MetricsResponse(
                total_runs=0,
                first_attempt_pass_rate=0.0,
                overall_pass_rate=0.0,
                retry_distribution={"0_retries": 0, "1_retry": 0, "2_retries": 0},
                avg_tokens_per_run=0.0,
                top_failing_criteria=[],
            )

        completed_runs = [r for r in all_runs if r.status == RunStatus.PASS.value]
        overall_pass_rate = round(len(completed_runs) / total_runs, 3)

        # First attempt pass = passing run where rejection logs count is 0
        first_pass_count = sum(1 for r in completed_runs if len(r.rejection_logs) == 0)
        first_attempt_pass_rate = round(first_pass_count / total_runs, 3)

        # Retry distribution
        retry_dist = {"0_retries": 0, "1_retry": 0, "2_retries": 0}
        for r in all_runs:
            retries = len(r.rejection_logs)
            if retries == 0:
                retry_dist["0_retries"] += 1
            elif retries == 1:
                retry_dist["1_retry"] += 1
            else:
                retry_dist["2_retries"] += 1

        # Token usage
        all_tokens = list(db.scalars(select(TokenUsageModel)).all())
        total_tokens = sum(t.total_tokens for t in all_tokens)
        avg_tokens = round(total_tokens / total_runs, 1)

        # Top failing criteria
        all_rejections = list(db.scalars(select(RejectionLogModel)).all())
        fail_counts: Dict[str, int] = {}
        for rej in all_rejections:
            for cid in rej.failed_criteria:
                fail_counts[cid] = fail_counts.get(cid, 0) + 1

        sorted_fails = sorted(fail_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        top_failing = [{"criterion_id": cid, "failure_count": cnt} for cid, cnt in sorted_fails]

        # Pass rate with vs without pitfall hint
        with_hint = [r for r in all_runs if r.hint_version and r.hint_version != "none"]
        without_hint = [r for r in all_runs if not r.hint_version or r.hint_version == "none"]

        pass_rate_with = (
            round(sum(1 for r in with_hint if r.status == RunStatus.PASS.value) / len(with_hint), 3)
            if with_hint
            else None
        )
        pass_rate_without = (
            round(sum(1 for r in without_hint if r.status == RunStatus.PASS.value) / len(without_hint), 3)
            if without_hint
            else None
        )

        return MetricsResponse(
            total_runs=total_runs,
            first_attempt_pass_rate=first_attempt_pass_rate,
            overall_pass_rate=overall_pass_rate,
            retry_distribution=retry_dist,
            avg_tokens_per_run=avg_tokens,
            top_failing_criteria=top_failing,
            pass_rate_with_hint=pass_rate_with,
            pass_rate_without_hint=pass_rate_without,
        )


@router.get("/config/rubric", dependencies=[Depends(verify_api_key)])
def get_rubric_config_endpoint() -> Dict[str, Any]:
    """Returns the current active evaluation rubric configuration."""
    rubric_path = Path(__file__).parent.parent / "evaluation" / "rubric.yaml"
    if not rubric_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rubric file not found.")

    with open(rubric_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data


# ==========================================
# Health & Readiness Probes (Public)
# ==========================================

@router.get("/health")
def health_endpoint() -> Dict[str, str]:
    """Liveness probe verifying that the API process is alive."""
    return {"status": "ok"}


@router.get("/ready")
def ready_endpoint() -> Dict[str, Any]:
    """Readiness probe checking database connectivity and provider configuration without spending tokens."""
    db_connected = False
    try:
        with get_db_context() as db:
            db.execute(text("SELECT 1"))
            db_connected = True
    except Exception as exc:
        logger.error("Readiness probe database check failed: %s", exc)

    model_available = bool(os.getenv("GROQ_API_KEY"))

    status_str = "ready" if db_connected else "not_ready"
    return {
        "status": status_str,
        "database": "connected" if db_connected else "disconnected",
        "model_available": model_available,
    }
