"""Shared Enumerations Module.

Purpose:
    Defines canonical enums for run statuses, rubric severities, claim types,
    evidence modes, and evaluation verdicts across the entire system.

Inputs/Outputs:
    Exports pure Enum definitions used by all layers.

What it must NOT do:
    - Must NOT import from api, ui, agent, or evaluation.
    - Must NOT perform any I/O or side-effects.
"""
from enum import Enum


class RunStatus(str, Enum):
    """Terminal and operational statuses for a lesson generation run."""
    RUNNING = "RUNNING"
    PASS = "PASS"
    REJECTED = "REJECTED"
    ERROR = "ERROR"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    CANCELLED = "CANCELLED"


class CriterionSeverity(str, Enum):
    """Severity levels for evaluation rubric criteria."""
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


class CriterionMethod(str, Enum):
    """Execution method for rubric evaluation."""
    DETERMINISTIC = "deterministic"
    LLM = "llm"


class CriterionStatus(str, Enum):
    """Pass/Fail evaluation status for each rubric criterion."""
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_CHECKED = "NOT_CHECKED"


class ClaimType(str, Enum):
    """Taxonomy of extracted claims."""
    FACTUAL = "factual"
    ILLUSTRATIVE = "illustrative"
    SUBJECTIVE = "subjective"
    MATHEMATICAL = "mathematical"
    CODE = "code"


class ClaimStatus(str, Enum):
    """Grounding verification verdict for a material claim against provided evidence."""
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNVERIFIABLE = "UNVERIFIABLE"


class EvidenceMode(str, Enum):
    """Operating mode determining whether external documents were supplied."""
    MODEL_KNOWLEDGE_ONLY = "MODEL_KNOWLEDGE_ONLY"
    PROVIDED_DOCS = "PROVIDED_DOCS"


class LearnerLevel(str, Enum):
    """Target learner audience level."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class LessonLength(str, Enum):
    """Target length profiles."""
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class CallType(str, Enum):
    """LLM invocation categories for token budget accounting."""
    GENERATE = "generate"
    REVISE = "revise"
    JUDGE = "judge"
    REPAIR = "repair"


class ProposalStatus(str, Enum):
    """Lifecycle statuses for approval-gated self-evolving proposals."""
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ACTIVE = "ACTIVE"
    ROLLED_BACK = "ROLLED_BACK"


class RetryResult(str, Enum):
    """Result logged in rejection audit trail entries."""
    PASS = "PASS"
    REJECTED = "REJECTED"
    RETRYING = "RETRYING"
