"""Memory and Persistence Store Module.

Purpose:
    Manages SQLAlchemy 2.x persistence for runs, versions, evaluations,
    rejection logs, token usages, user feedback, proposals, and prompt versions.
    Implements Level A static pitfall hints and Level B proposal state tracking.

Inputs/Outputs:
    Inputs: Session instances, run configurations, evaluation metrics.
    Outputs: Persisted ORM models, audit metrics, aggregated pitfall hints.

What it must NOT do:
    - Must NOT allow free-form LLM text in Level A pitfall hints (static templates only).
    - Must NOT automatically approve or activate Level B proposals.
    - Must NOT import UI or API transport logic.
"""
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    select,
    update,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from shared.enums import ProposalStatus, RunStatus

DEFAULT_DB_URL = "sqlite:///./lesson_generator.db"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)


class Base(DeclarativeBase):
    """Base declarative model."""
    pass


def get_utc_now() -> datetime:
    """Returns current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


# ==========================================
# Database ORM Models
# ==========================================

class RunModel(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    topic: Mapped[str] = mapped_column(String(300), nullable=False)
    learner_level: Mapped[str] = mapped_column(String(50), nullable=False)
    objectives: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    target_length: Mapped[str] = mapped_column(String(50), nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=RunStatus.RUNNING.value)
    self_judged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    not_externally_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    hint_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    final_lesson_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now)

    versions: Mapped[List["LessonVersionModel"]] = relationship(
        "LessonVersionModel", back_populates="run", cascade="all, delete-orphan", order_by="LessonVersionModel.version_number"
    )
    evaluations: Mapped[List["EvaluationModel"]] = relationship(
        "EvaluationModel", back_populates="run", cascade="all, delete-orphan"
    )
    rejection_logs: Mapped[List["RejectionLogModel"]] = relationship(
        "RejectionLogModel", back_populates="run", cascade="all, delete-orphan", order_by="RejectionLogModel.attempt"
    )
    tokens: Mapped[List["TokenUsageModel"]] = relationship(
        "TokenUsageModel", back_populates="run", cascade="all, delete-orphan"
    )
    feedbacks: Mapped[List["FeedbackModel"]] = relationship(
        "FeedbackModel", back_populates="run", cascade="all, delete-orphan"
    )


class LessonVersionModel(Base):
    __tablename__ = "lesson_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("runs.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    changes_made: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now)

    run: Mapped["RunModel"] = relationship("RunModel", back_populates="versions")
    evaluations: Mapped[List["EvaluationModel"]] = relationship(
        "EvaluationModel", back_populates="lesson_version", cascade="all, delete-orphan"
    )


class EvaluationModel(Base):
    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("runs.id"), nullable=False)
    lesson_version_id: Mapped[str] = mapped_column(String(36), ForeignKey("lesson_versions.id"), nullable=False)
    rubric_version: Mapped[str] = mapped_column(String(20), nullable=False)
    judge_model: Mapped[str] = mapped_column(String(100), nullable=False)
    criterion_results: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False)
    claims: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now)

    run: Mapped["RunModel"] = relationship("RunModel", back_populates="evaluations")
    lesson_version: Mapped["LessonVersionModel"] = relationship("LessonVersionModel", back_populates="evaluations")


class RejectionLogModel(Base):
    __tablename__ = "rejection_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("runs.id"), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    failed_criteria: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    reasons: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    changes_made: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    result: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now)

    run: Mapped["RunModel"] = relationship("RunModel", back_populates="rejection_logs")


class TokenUsageModel(Base):
    __tablename__ = "token_usage"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("runs.id"), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    call_type: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    is_estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now)

    run: Mapped["RunModel"] = relationship("RunModel", back_populates="tokens")


class FeedbackModel(Base):
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("runs.id"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    issue_tags: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now)

    run: Mapped["RunModel"] = relationship("RunModel", back_populates="feedbacks")


class ProposalModel(Base):
    __tablename__ = "proposals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    target: Mapped[str] = mapped_column(String(100), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    proposed_change: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=ProposalStatus.PROPOSED.value)
    approved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rollback_of: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now)


class PromptVersionModel(Base):
    __tablename__ = "prompt_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prompt_name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now)


# ==========================================
# Static Pitfalls (Level A: Static Templates)
# ==========================================

STATIC_PITFALL_TEMPLATES: Dict[str, str] = {
    "output_integrity": "Ensure all required fields are non-empty and word count strictly matches the target range.",
    "beginner_readability": "Keep sentence structure simple; decompose compound clauses to avoid elevated grade levels.",
    "jargon_control": "Ensure every specialized term is defined inline at first mention or added to the glossary.",
    "example_present": "Ensure the worked example scenario is explicitly referenced in instructional steps or summary.",
    "teaching_flow_structure": "Maintain sequential step ordering with non-empty headings and bodies.",
    "code_integrity": "Verify all embedded Python code blocks have valid syntax and parse without SyntaxError.",
    "citation_integrity": "Only cite supplied sources; do not fabricate external URLs or non-existent papers.",
    "factual_accuracy": "Ensure core mechanisms, facts, and definitions are mathematically and scientifically sound.",
    "internal_consistency": "Check that definitions and walkthroughs do not contradict one another across sections.",
    "example_correctness": "Verify that worked example walkthrough demonstrates the concept accurately and feasibly.",
    "topic_coverage": "Substantively address all stated learning objectives within the instructional steps.",
    "coherence_of_flow": "Ensure smooth conceptual progression between prerequisites and core definition.",
    "standalone_completeness": "Provide sufficient context so no prerequisite is left unaddressed.",
}


def get_common_pitfalls_hint(db: Session, limit_runs: int = 50, token_cap: int = 150) -> tuple[str, str]:
    """Aggregates the top 3 failing criteria over recent runs and formats a static pitfall hint.

    Args:
        db: Database session.
        limit_runs: Window of historical runs to audit.
        token_cap: Upper token ceiling (~150 tokens).

    Returns:
        Tuple of (formatted_hint_string, hint_version).
    """
    stmt = (
        select(RejectionLogModel)
        .order_by(RejectionLogModel.created_at.desc())
        .limit(limit_runs * 2)
    )
    records = list(db.scalars(stmt).all())
    if not records:
        return ("", "none")

    failure_counts: Dict[str, int] = {}
    for r in records:
        for cid in r.failed_criteria:
            failure_counts[cid] = failure_counts.get(cid, 0) + 1

    if not failure_counts:
        return ("", "none")

    sorted_criteria = sorted(failure_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    top_cids = [cid for cid, _ in sorted_criteria]

    hints = []
    for cid in top_cids:
        template = STATIC_PITFALL_TEMPLATES.get(cid)
        if template:
            hints.append(f"- Focus on {cid}: {template}")

    hint_text = "\n".join(hints)
    # Estimate rough word count to ensure <= 150 tokens
    words = hint_text.split()
    if len(words) > 100:
        hint_text = " ".join(words[:100]) + "..."

    hint_version = f"pitfalls-v1-{'-'.join(top_cids)}"
    return (hint_text, hint_version)


# ==========================================
# Lifecycle & Recovery Helpers
# ==========================================

def init_db() -> None:
    """Initializes SQLite schema tables."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Yields managed database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Context manager for standalone execution."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def recover_stale_running_runs() -> int:
    """Marks any runs stranded in RUNNING status at startup as ERROR."""
    with get_db_context() as db:
        stmt = (
            update(RunModel)
            .where(RunModel.status == RunStatus.RUNNING.value)
            .values(
                status=RunStatus.ERROR.value,
                error_message="Server restarted or terminated while run was in progress.",
            )
        )
        res = db.execute(stmt)
        return int(getattr(res, "rowcount", 0))
