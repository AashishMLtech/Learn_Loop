"""Lesson Generator Service Module.

Purpose:
    Coordinates synthesis of standalone beginner lessons and targeted revisions
    using the swappable LLMClientInterface, enforcing token tracking and schema validation.

Inputs/Outputs:
    Inputs: Topic, level, objectives, target length, optional reference context, failure feedback.
    Outputs: Validated Lesson or LessonRevisionOutput objects.

What it must NOT do:
    - Must NOT bypass the TokenBudgetTracker.
    - Must NOT hardcode topics or demo content.
    - Must NOT perform rubric evaluation or release gating.
"""
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from generation.schema import Lesson, LessonRevisionOutput
from shared.enums import CallType
from shared.llm_client import LLMClientInterface, TokenBudgetTracker

logger = logging.getLogger("lesson_generator.generation_service")
PROMPTS_DIR = Path(__file__).parent / "prompts"


def parse_json_from_llm(raw_text: str) -> Dict[str, Any]:
    """Extracts and parses a JSON dictionary from raw LLM output.

    Args:
        raw_text: String response from the model.

    Returns:
        Parsed dictionary.

    Raises:
        ValueError: If valid JSON cannot be extracted.
    """
    text = raw_text.strip()
    if not text:
        raise ValueError("LLM response was completely empty.")

    # Strip markdown code fences if present
    fence_pattern = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL | re.IGNORECASE)
    match = fence_pattern.match(text)
    if match:
        text = match.group(1).strip()
    else:
        start_idx = text.find("{")
        end_idx = text.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            text = text[start_idx : end_idx + 1]

    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object, got {type(data).__name__}")
        return data
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to decode JSON from model response: {exc}") from exc


class GeneratorService:
    """Service executing initial lesson creation and targeted revisions."""

    def __init__(self, llm_client: LLMClientInterface, model: str = ""):
        """Initializes generator service with an LLM client and model ID.

        Args:
            llm_client: Swappable LLMClientInterface implementation.
            model: Model identifier. Defaults to client configured model.
        """
        self.client = llm_client
        self.model = model or getattr(llm_client, "model", "") or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        self.generate_prompt_template = (PROMPTS_DIR / "generate.md").read_text(encoding="utf-8")
        self.revise_prompt_template = (PROMPTS_DIR / "revise.md").read_text(encoding="utf-8")

    def generate(
        self,
        topic: str,
        learner_level: str,
        learning_objectives: List[str],
        target_length: str,
        supplied_sources: Optional[List[Dict[str, str]]] = None,
        reference_context: str = "",
        pitfall_hints: str = "None recorded.",
        token_tracker: Optional[TokenBudgetTracker] = None,
        attempt: int = 1,
    ) -> Lesson:
        """Generates an initial lesson draft.

        Args:
            topic: Educational subject to teach.
            learner_level: Target expertise level.
            learning_objectives: List of instructional goals.
            target_length: Length profile (short, medium, long).
            supplied_sources: Authorized sources list.
            reference_context: Sanitized external documentation context.
            pitfall_hints: Historical common pitfall hints.
            token_tracker: Token budget manager.
            attempt: Current attempt counter.

        Returns:
            Validated Lesson object.

        Raises:
            BudgetExhaustedError: If token budget is depleted.
            ValueError: If output schema validation fails.
        """
        if token_tracker:
            token_tracker.assert_budget_available()

        sources_str = (
            "\n".join(f"- [{s.get('source_id')}]: {s.get('title')}" for s in (supplied_sources or []))
            if supplied_sources
            else "None supplied."
        )

        prompt = self.generate_prompt_template.format(
            topic=topic,
            learner_level=learner_level,
            learning_objectives="\n".join(f"- {obj}" for obj in learning_objectives),
            target_length=target_length,
            pitfall_hints=pitfall_hints or "None recorded.",
            supplied_sources=sources_str,
            reference_context=reference_context or "No reference document provided.",
        )

        messages = [
            {"role": "system", "content": "You are an expert instructional designer and technical educator."},
            {"role": "user", "content": prompt},
        ]

        response = self.client.generate(
            messages=messages,
            model=self.model,
            temperature=0.7,
            json_mode=True,
        )

        if token_tracker:
            token_tracker.record_usage(
                attempt=attempt,
                call_type=CallType.GENERATE,
                model=self.model,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                total_tokens=response.total_tokens,
                is_estimated=False,
            )

        data = parse_json_from_llm(response.content)
        try:
            return Lesson.model_validate(data)
        except ValidationError as exc:
            raise ValueError(f"Generated output failed Lesson schema validation: {exc}") from exc

    def revise(
        self,
        topic: str,
        learner_level: str,
        learning_objectives: List[str],
        previous_lesson: Lesson,
        failure_feedback: str,
        token_tracker: Optional[TokenBudgetTracker] = None,
        attempt: int = 2,
    ) -> LessonRevisionOutput:
        """Generates a revised lesson draft in response to specific evaluation failures.

        Args:
            topic: Educational subject.
            learner_level: Target expertise level.
            learning_objectives: List of instructional goals.
            previous_lesson: Prior failed lesson draft.
            failure_feedback: Compact summary of failed criteria and reasons.
            token_tracker: Token budget manager.
            attempt: Current attempt counter.

        Returns:
            LessonRevisionOutput containing revised Lesson and changes_made list.

        Raises:
            BudgetExhaustedError: If token budget is depleted.
            ValueError: If output schema validation fails.
        """
        if token_tracker:
            token_tracker.assert_budget_available()

        prompt = self.revise_prompt_template.format(
            topic=topic,
            learner_level=learner_level,
            learning_objectives="\n".join(f"- {obj}" for obj in learning_objectives),
            previous_lesson_json=previous_lesson.model_dump_json(indent=2),
            failure_feedback=failure_feedback,
        )

        messages = [
            {"role": "system", "content": "You are an expert educational editor improving flawed drafts."},
            {"role": "user", "content": prompt},
        ]

        response = self.client.generate(
            messages=messages,
            model=self.model,
            temperature=0.4,
            json_mode=True,
        )

        if token_tracker:
            token_tracker.record_usage(
                attempt=attempt,
                call_type=CallType.REVISE,
                model=self.model,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                total_tokens=response.total_tokens,
                is_estimated=False,
            )

        data = parse_json_from_llm(response.content)
        try:
            return LessonRevisionOutput.model_validate(data)
        except ValidationError as exc:
            raise ValueError(f"Revision output failed LessonRevisionOutput schema validation: {exc}") from exc
