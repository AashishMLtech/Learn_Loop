"""LLM Judge Evaluation Service Module.

Purpose:
    Executes the single combined structured LLM evaluation call at temperature 0.0,
    evaluating pedagogical criteria and extracting claims with one format-repair re-ask
    and strict caching.

Inputs/Outputs:
    Inputs: Lesson, learning objectives, retrieved evidence context, token tracker.
    Outputs: Validated JudgeOutput containing criteria_results and claims.

What it must NOT do:
    - Must NOT evaluate readability or jargon (handled deterministically).
    - Must NOT perform more than one format-repair re-ask.
    - Must NOT reuse stale cache entries from previous versions.
"""
import hashlib
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError

from evaluation.validators import CriterionResult
from generation.schema import Lesson
from generation.service import parse_json_from_llm
from shared.enums import CallType, ClaimStatus, ClaimType
from shared.llm_client import LLMClientInterface, TokenBudgetTracker

logger = logging.getLogger("lesson_generator.judge")
PROMPTS_DIR = Path(__file__).parent / "prompts"

MANDATORY_JUDGE_CRITERIA = {
    "factual_accuracy",
    "internal_consistency",
    "example_correctness",
    "topic_coverage",
    "coherence_of_flow",
    "standalone_completeness",
}


class Claim(BaseModel):
    """An extracted claim statement from the lesson."""
    id: str = Field(..., description="Unique claim identifier, e.g. claim-1")
    text: str = Field(..., description="Claim statement")
    type: ClaimType = Field(default=ClaimType.FACTUAL, description="Claim taxonomy category")
    section: str = Field(..., description="Lesson section where claim appears")
    material: bool = Field(default=True, description="Whether claim is material to topic")
    status: ClaimStatus = Field(default=ClaimStatus.UNVERIFIABLE, description="Grounding status")
    source_id: Optional[str] = Field(default=None, description="Matching source identifier")
    evidence_quote: Optional[str] = Field(default=None, description="Direct quote from source")


class JudgeOutput(BaseModel):
    """Combined structured output schema from the LLM judge."""
    criteria_results: List[CriterionResult] = Field(..., description="Results for the 6 LLM-judged criteria")
    claims: List[Claim] = Field(default_factory=list, description="Extracted claims")


class JudgeEvaluationError(Exception):
    """Raised when the judge output is malformed or invalid after format repair."""
    pass


def compute_judge_cache_key(
    lesson_text: str,
    rubric_version: str = "1.0.0",
    prompt_version: str = "1.0.0",
    evidence_hash: str = "none",
) -> str:
    """Computes a deterministic cache key for judge evaluation results.

    Args:
        lesson_text: Full concatenated text of the lesson version.
        rubric_version: Version of the evaluation rubric.
        prompt_version: Version of the judge prompt template.
        evidence_hash: SHA256 hash of provided reference documents.

    Returns:
        Hex-encoded SHA-256 string.
    """
    raw = f"{lesson_text}::{rubric_version}::{prompt_version}::{evidence_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class JudgeService:
    """Evaluates pedagogical quality of a lesson via structured zero-temperature LLM completion."""

    def __init__(self, llm_client: LLMClientInterface, model: str = ""):
        """Initializes judge service.

        Args:
            llm_client: LLMClientInterface provider instance.
            model: Judge model identifier. Defaults to client configured model.
        """
        self.client = llm_client
        self.model = model or getattr(llm_client, "model", "") or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        self.judge_prompt_template = (PROMPTS_DIR / "judge.md").read_text(encoding="utf-8")
        self._cache: Dict[str, JudgeOutput] = {}

    def _validate_completeness(self, output: JudgeOutput) -> None:
        """Asserts all 6 mandatory judge criteria are present in output.

        Args:
            output: Parsed JudgeOutput.

        Raises:
            JudgeEvaluationError: If any mandatory criteria are missing.
        """
        found = {r.criterion_id for r in output.criteria_results}
        missing = MANDATORY_JUDGE_CRITERIA - found
        if missing:
            raise JudgeEvaluationError(f"Judge output missing mandatory criteria: {', '.join(missing)}")

    def judge(
        self,
        topic: str,
        learning_objectives: List[str],
        lesson: Lesson,
        reference_evidence_context: str = "No reference document provided.",
        evidence_hash: str = "none",
        token_tracker: Optional[TokenBudgetTracker] = None,
        attempt: int = 1,
    ) -> JudgeOutput:
        """Executes the judge call with format repair and result caching.

        Args:
            topic: Educational subject.
            learning_objectives: List of learning objectives.
            lesson: Current Lesson draft.
            reference_evidence_context: Delimited retrieved excerpts.
            evidence_hash: Hash of reference documentation.
            token_tracker: Token budget manager.
            attempt: Current attempt counter.

        Returns:
            Validated JudgeOutput.

        Raises:
            BudgetExhaustedError: If token budget is depleted.
            JudgeEvaluationError: If output remains malformed after format repair.
        """
        cache_key = compute_judge_cache_key(
            lesson_text=lesson.full_text(),
            rubric_version="1.0.0",
            prompt_version="1.0.0",
            evidence_hash=evidence_hash,
        )

        if cache_key in self._cache:
            logger.info("Judge cache hit for key %s", cache_key[:12])
            return self._cache[cache_key]

        if token_tracker:
            token_tracker.assert_budget_available()

        prompt = self.judge_prompt_template.format(
            topic=topic,
            learning_objectives="\n".join(f"- {obj}" for obj in learning_objectives),
            lesson_json=lesson.model_dump_json(indent=2),
            reference_evidence_context=reference_evidence_context,
        )

        messages = [
            {"role": "system", "content": "You are an objective academic evaluator."},
            {"role": "user", "content": prompt},
        ]

        # Call 1: Primary judge invocation (temp 0)
        response = self.client.generate(
            messages=messages,
            model=self.model,
            temperature=0.0,
            json_mode=True,
        )

        if token_tracker:
            token_tracker.record_usage(
                attempt=attempt,
                call_type=CallType.JUDGE,
                model=self.model,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                total_tokens=response.total_tokens,
                is_estimated=False,
            )

        try:
            data = parse_json_from_llm(response.content)
            output = JudgeOutput.model_validate(data)
            self._validate_completeness(output)
            self._cache[cache_key] = output
            return output
        except (ValueError, ValidationError, JudgeEvaluationError) as first_err:
            logger.warning("Judge call returned malformed output (%s). Executing format-repair re-ask.", first_err)

        # Single format-repair re-ask (counted in token budget, NOT as a lesson retry)
        if token_tracker:
            token_tracker.assert_budget_available()

        repair_messages = list(messages)
        repair_messages.append({"role": "assistant", "content": response.content})
        repair_messages.append({
            "role": "user",
            "content": (
                "Your previous response was malformed or missing required criteria. "
                "Output valid JSON containing ALL 6 criteria: factual_accuracy, internal_consistency, "
                "example_correctness, topic_coverage, coherence_of_flow, standalone_completeness, and claims[]."
            ),
        })

        repair_response = self.client.generate(
            messages=repair_messages,
            model=self.model,
            temperature=0.0,
            json_mode=True,
        )

        if token_tracker:
            token_tracker.record_usage(
                attempt=attempt,
                call_type=CallType.REPAIR,
                model=self.model,
                prompt_tokens=repair_response.prompt_tokens,
                completion_tokens=repair_response.completion_tokens,
                total_tokens=repair_response.total_tokens,
                is_estimated=False,
            )

        try:
            repair_data = parse_json_from_llm(repair_response.content)
            repaired_output = JudgeOutput.model_validate(repair_data)
            self._validate_completeness(repaired_output)
            self._cache[cache_key] = repaired_output
            return repaired_output
        except Exception as second_err:
            raise JudgeEvaluationError(
                f"Judge output remained malformed after format repair re-ask: {second_err}"
            ) from second_err
