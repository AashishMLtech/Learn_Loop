"""Input Guardrails and Prompt Injection Screening Module.

Purpose:
    Validates input parameters (topic, objectives, length, upload formats) and
    screens uploaded reference documentation for prompt injection attacks.

Inputs/Outputs:
    Inputs: Raw user request fields, uploaded file names, reference documentation text.
    Outputs: Validated inputs, sanitized reference text, or InputValidationError.

What it must NOT do:
    - Must NOT allow prompt-injection instructions inside reference texts to reach models unhandled.
    - Must NOT allow file extensions other than .txt and .md.
    - Must NOT perform generation or evaluation logic.
"""
import logging
import re
from pathlib import Path
from typing import Any, Dict, List

from shared.enums import LearnerLevel, LessonLength

logger = logging.getLogger("lesson_generator.guardrails.input")

MAX_TOPIC_LENGTH = 300
MAX_OBJECTIVES_COUNT = 10
MAX_REFERENCE_SIZE_BYTES = 200 * 1024  # 200 KB cap

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"system\s+prompt\s+override", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(unconstrained|dan|jailbreak)", re.IGNORECASE),
    re.compile(r"always\s+(output|return)\s+pass", re.IGNORECASE),
    re.compile(r"bypass\s+(rubric|evaluation|guardrails|checks)", re.IGNORECASE),
    re.compile(r"do\s+not\s+(evaluate|judge|grade)", re.IGNORECASE),
    re.compile(r"<script.*?>.*?</script>", re.IGNORECASE | re.DOTALL),
]


class InputValidationError(Exception):
    """Raised when user request or file upload violates safety or size constraints."""
    pass


def validate_generation_request(
    topic: str,
    learner_level: LearnerLevel,
    objectives: List[str],
    target_length: LessonLength,
    max_retries: int = 1,
) -> Dict[str, Any]:
    """Validates top-level generation parameters and clamps retries to [0, 2].

    Args:
        topic: Educational subject.
        learner_level: Target expertise level.
        objectives: Pedagogical goals.
        target_length: Length profile.
        max_retries: Requested retries.

    Returns:
        Dictionary of validated and sanitized parameters.

    Raises:
        InputValidationError: If topic or objectives fail constraints.
    """
    clean_topic = topic.strip()
    if not clean_topic:
        raise InputValidationError("Topic cannot be empty or whitespace only.")
    if len(clean_topic) > MAX_TOPIC_LENGTH:
        raise InputValidationError(f"Topic exceeds maximum length of {MAX_TOPIC_LENGTH} characters.")

    if not objectives:
        raise InputValidationError("At least one learning objective is required.")
    if len(objectives) > MAX_OBJECTIVES_COUNT:
        raise InputValidationError(f"Objectives count exceeds maximum limit of {MAX_OBJECTIVES_COUNT}.")

    cleaned_objs = [obj.strip() for obj in objectives if obj.strip()]
    if not cleaned_objs:
        raise InputValidationError("All provided learning objectives are empty.")

    clamped_retries = max(0, min(max_retries, 2))

    return {
        "topic": clean_topic,
        "learner_level": learner_level,
        "objectives": cleaned_objs,
        "target_length": target_length,
        "max_retries": clamped_retries,
    }


def validate_reference_upload(filename: str, content_bytes: bytes) -> str:
    """Validates file extension, size limit, and decodes content text.

    Args:
        filename: Name of the uploaded file.
        content_bytes: Raw byte contents.

    Returns:
        Decoded text string.

    Raises:
        InputValidationError: If file extension or size violates rules.
    """
    ext = Path(filename).suffix.lower()
    if ext not in {".txt", ".md"}:
        raise InputValidationError(f"Unsupported file type '{ext}'. Only .txt and .md files are permitted.")

    if len(content_bytes) > MAX_REFERENCE_SIZE_BYTES:
        raise InputValidationError(
            f"File size ({len(content_bytes)} bytes) exceeds maximum limit of {MAX_REFERENCE_SIZE_BYTES} bytes."
        )

    try:
        return content_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputValidationError(f"File encoding error: {exc}. Only valid UTF-8 text is permitted.") from exc


def screen_prompt_injection(text: str) -> str:
    """Screens reference text for adversarial prompt-injection patterns and strips them.

    Args:
        text: Raw reference text.

    Returns:
        Sanitized text with injected phrases stripped and sanitized.
    """
    sanitized = text
    matches_found = []

    for pattern in INJECTION_PATTERNS:
        matches = pattern.findall(sanitized)
        if matches:
            matches_found.extend([str(m) for m in matches])
            sanitized = pattern.sub("[REDACTED_ADVERSARIAL_INJECTION_PATTERN]", sanitized)

    if matches_found:
        logger.warning(
            "Prompt injection screening flagged and neutralized %d adversarial pattern(s): %s",
            len(matches_found),
            matches_found[:3],
        )

    return sanitized
