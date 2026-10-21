"""LangGraph State Definition Module.

Purpose:
    Declares the strongly-typed AgentState dictionary governing data flow
    across nodes in the lesson generation and evaluation state machine.

Inputs/Outputs:
    Inputs: Request specifications, retrieved documents, execution flags.
    Outputs: State mutations across pipeline nodes.

What it must NOT do:
    - Must NOT import UI or API transport logic.
    - Must NOT contain database session objects directly in state.
"""
from typing import Any, Dict, List, Optional, TypedDict

from evaluation.judge import JudgeOutput
from evaluation.validators import CriterionResult
from generation.schema import Lesson
from guardrails.release_gate import ReleaseDecision
from shared.enums import EvidenceMode, LearnerLevel, LessonLength, RunStatus
from shared.llm_client import TokenBudgetTracker


class AgentState(TypedDict, total=False):
    """Strongly-typed execution state tracked across the LangGraph state machine."""
    run_id: str
    topic: str
    learner_level: LearnerLevel
    learning_objectives: List[str]
    target_length: LessonLength
    max_retries: int
    supplied_sources: List[Dict[str, str]]
    reference_context: str
    evidence_mode: EvidenceMode
    evidence_hash: str
    pitfall_hints: str
    hint_version: str

    # Cancellation flag checked before LLM invocations
    cancel_requested: bool

    # Iteration tracking
    current_attempt: int
    current_version_number: int
    current_version_id: Optional[str]
    current_lesson: Optional[Lesson]
    current_changes_made: List[str]
    deterministic_failed: bool
    failed_criteria_feedback: Optional[str]

    # Evaluation results for the current version
    deterministic_results: List[CriterionResult]
    judge_output: Optional[JudgeOutput]
    all_criterion_results: List[CriterionResult]
    release_decision: Optional[ReleaseDecision]

    # Rejection audit log
    rejection_log: List[Dict[str, Any]]

    # Terminal state
    status: RunStatus
    error_message: Optional[str]

    # Token accounting and service registry
    token_tracker: TokenBudgetTracker
    services: Dict[str, Any]
