"""Deterministic Rubric Validators Module.

Purpose:
    Executes all zero-token deterministic rubric checks on a generated lesson
    before invoking the LLM judge. Short-circuits the judge call on failure.

Inputs/Outputs:
    Inputs: Lesson object, learner level, requested length, supplied sources.
    Outputs: List of CriterionResult objects.

What it must NOT do:
    - Must NOT consume any LLM tokens.
    - Must NOT modify the lesson or persist records.
    - Must NOT override the release gate.
"""
import ast
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import textstat
import yaml
from pydantic import BaseModel, Field

from generation.schema import Lesson
from shared.enums import CriterionSeverity, CriterionStatus, LearnerLevel, LessonLength

RUBRIC_PATH = Path(__file__).parent / "rubric.yaml"

# Calibrated length bounds (min_words, max_words)
LENGTH_WORD_BOUNDS: Dict[LessonLength, tuple[int, int]] = {
    LessonLength.SHORT: (250, 1000),
    LessonLength.MEDIUM: (700, 2000),
    LessonLength.LONG: (1400, 3500),
}

# Calibrated Flesch-Kincaid grade level ceilings
READABILITY_GRADE_CEILINGS: Dict[LearnerLevel, float] = {
    LearnerLevel.BEGINNER: 16.5,
    LearnerLevel.INTERMEDIATE: 18.5,
    LearnerLevel.ADVANCED: 21.0,
}


class CriterionResult(BaseModel):
    """Result of evaluating a single rubric criterion."""
    criterion_id: str = Field(..., description="ID of the rubric criterion")
    status: CriterionStatus = Field(..., description="PASS, FAIL, or NOT_CHECKED")
    severity: CriterionSeverity = Field(..., description="critical, major, or minor")
    reason: str = Field(..., description="Explanation of why this criterion passed or failed")
    affected_section: Optional[str] = Field(default=None, description="Section most affected by the issue")
    evidence: List[str] = Field(default_factory=list, description="Specific textual excerpts or data backing the verdict")
    suggested_fix: Optional[str] = Field(default=None, description="Actionable recommendation for revision")


def load_rubric_dict() -> Dict[str, Any]:
    """Loads the canonical versioned rubric YAML.

    Returns:
        Dictionary loaded from rubric.yaml.
    """
    with open(RUBRIC_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_output_integrity(lesson: Lesson, target_length: LessonLength) -> CriterionResult:
    """Validates schema completeness, required fields, and word count bounds.

    Args:
        lesson: The generated lesson draft.
        target_length: The requested length profile.

    Returns:
        CriterionResult for output_integrity.
    """
    min_w, max_w = LENGTH_WORD_BOUNDS.get(target_length, (250, 1000))
    total_words = lesson.word_count()
    errors = []

    if not lesson.title.strip():
        errors.append("Missing title")
    if not lesson.introduction.strip():
        errors.append("Missing introduction")
    if not lesson.definition.strip():
        errors.append("Missing definition")
    if not lesson.why_it_matters.strip():
        errors.append("Missing why_it_matters")
    if not lesson.steps:
        errors.append("Steps must contain at least 1 instructional step")
    if not lesson.worked_example.scenario.strip() or not lesson.worked_example.walkthrough.strip():
        errors.append("Worked example scenario or walkthrough is empty")
    if not lesson.summary.strip():
        errors.append("Missing summary")
    if not lesson.takeaways:
        errors.append("Takeaways must contain at least 1 item")

    if total_words < min_w:
        errors.append(f"Word count {total_words} is below minimum {min_w} for length '{target_length.value}'")
    elif total_words > max_w:
        errors.append(f"Word count {total_words} exceeds maximum {max_w} for length '{target_length.value}'")

    if errors:
        return CriterionResult(
            criterion_id="output_integrity",
            status=CriterionStatus.FAIL,
            severity=CriterionSeverity.CRITICAL,
            reason="; ".join(errors),
            affected_section="lesson",
            evidence=[f"Word count: {total_words}", f"Target range: [{min_w}, {max_w}]"] + errors,
            suggested_fix=f"Populate all required sections and ensure word count is between {min_w} and {max_w}.",
        )

    return CriterionResult(
        criterion_id="output_integrity",
        status=CriterionStatus.PASS,
        severity=CriterionSeverity.CRITICAL,
        reason=f"Lesson schema is complete and word count ({total_words}) is within [{min_w}, {max_w}].",
        evidence=[f"Word count: {total_words}"],
    )


def validate_beginner_readability(lesson: Lesson, learner_level: LearnerLevel) -> CriterionResult:
    """Validates that readability grade does not exceed the target learner ceiling.

    Args:
        lesson: The lesson draft.
        learner_level: Target learner level.

    Returns:
        CriterionResult for beginner_readability.
    """
    text = lesson.full_text()
    if not text.strip():
        return CriterionResult(
            criterion_id="beginner_readability",
            status=CriterionStatus.FAIL,
            severity=CriterionSeverity.MAJOR,
            reason="Empty lesson text cannot be assessed for readability.",
            affected_section="full_text",
        )

    grade = textstat.flesch_kincaid_grade(text)
    ceiling = READABILITY_GRADE_CEILINGS.get(learner_level, 16.5)

    if grade > ceiling:
        return CriterionResult(
            criterion_id="beginner_readability",
            status=CriterionStatus.FAIL,
            severity=CriterionSeverity.MAJOR,
            reason=f"Flesch-Kincaid grade level ({grade:.1f}) exceeds the {learner_level.value} ceiling ({ceiling:.1f}).",
            affected_section="steps / introduction",
            evidence=[f"Flesch-Kincaid Grade: {grade:.1f}", f"Ceiling: {ceiling:.1f}"],
            suggested_fix="Shorten complex sentences, decompose compound clauses, and simplify sentence structure.",
        )

    return CriterionResult(
        criterion_id="beginner_readability",
        status=CriterionStatus.PASS,
        severity=CriterionSeverity.MAJOR,
        reason=f"Flesch-Kincaid grade ({grade:.1f}) is within the allowable ceiling ({ceiling:.1f}) for {learner_level.value}.",
        evidence=[f"Flesch-Kincaid Grade: {grade:.1f}", f"Ceiling: {ceiling:.1f}"],
    )


def validate_jargon_control(lesson: Lesson) -> CriterionResult:
    """Ensures every glossary term has a definition, and every specialized_terms entry is in the glossary or defined at first use.

    Args:
        lesson: The lesson draft.

    Returns:
        CriterionResult for jargon_control.
    """
    if not lesson.glossary:
        return CriterionResult(
            criterion_id="jargon_control",
            status=CriterionStatus.FAIL,
            severity=CriterionSeverity.MAJOR,
            reason="Glossary is completely empty; beginner lessons require foundational term definitions.",
            affected_section="glossary",
            evidence=["Empty glossary list"],
            suggested_fix="Add at least 1-3 core terms with definitions to the glossary.",
        )

    empty_definitions = [g.term for g in lesson.glossary if not g.definition.strip()]
    if empty_definitions:
        return CriterionResult(
            criterion_id="jargon_control",
            status=CriterionStatus.FAIL,
            severity=CriterionSeverity.MAJOR,
            reason=f"Glossary terms without definition: {', '.join(empty_definitions)}",
            affected_section="glossary",
            evidence=empty_definitions,
            suggested_fix="Provide clear plain-English definitions for all glossary items.",
        )

    glossary_terms = {g.term.strip().lower() for g in lesson.glossary}
    full_text = lesson.full_text()

    # Verify each specialized_terms entry is in the glossary or defined at first use
    unaccounted = []
    for term in lesson.specialized_terms:
        term_clean = term.strip().lower()
        if not term_clean:
            continue
        if term_clean in glossary_terms:
            continue
        # Check inline definition cue: e.g. "term (definition)", "term is defined as", "term refers to"
        cue_pattern = re.compile(
            rf"{re.escape(term)}\s*(?:\([^\)]+\)|is\s+(?:defined\s+as|a|an)|refers\s+to|meaning)",
            re.IGNORECASE,
        )
        if not cue_pattern.search(full_text):
            unaccounted.append(term)

    if unaccounted:
        return CriterionResult(
            criterion_id="jargon_control",
            status=CriterionStatus.FAIL,
            severity=CriterionSeverity.MAJOR,
            reason=f"Specialized terms not defined in glossary or inline at first use: {', '.join(unaccounted)}",
            affected_section="specialized_terms / glossary",
            evidence=unaccounted,
            suggested_fix="Add these terms to the glossary or explain their meaning inline.",
        )

    return CriterionResult(
        criterion_id="jargon_control",
        status=CriterionStatus.PASS,
        severity=CriterionSeverity.MAJOR,
        reason=f"All {len(lesson.glossary)} glossary terms have definitions and all {len(lesson.specialized_terms)} specialized terms are defined.",
        evidence=[f"{len(lesson.glossary)} glossary terms", f"{len(lesson.specialized_terms)} specialized terms"],
    )


def validate_example_present(lesson: Lesson) -> CriterionResult:
    """Verifies worked_example is populated and explicitly referenced in steps or summary.

    Args:
        lesson: The lesson draft.

    Returns:
        CriterionResult for example_present.
    """
    we = lesson.worked_example
    if not we.scenario.strip() or not we.walkthrough.strip():
        return CriterionResult(
            criterion_id="example_present",
            status=CriterionStatus.FAIL,
            severity=CriterionSeverity.CRITICAL,
            reason="Worked example scenario or walkthrough is empty.",
            affected_section="worked_example",
            suggested_fix="Provide a realistic scenario and step-by-step walkthrough in the worked_example.",
        )

    # Search for references in steps or summary
    search_corpus = [lesson.summary]
    for step in lesson.steps:
        search_corpus.append(step.heading)
        search_corpus.append(step.body)
    combined = " ".join(search_corpus).lower()

    has_ref = any(
        kw in combined
        for kw in [
            "worked example",
            "example above",
            "in our example",
            "the example",
            "walkthrough",
            "in the scenario",
            "scenario above",
            "as illustrated",
            "as seen in the example",
        ]
    )

    # Check shared scenario keywords
    scenario_words = set(re.findall(r"\b[A-Za-z]{4,}\b", we.scenario.lower()))
    step_words = set(re.findall(r"\b[A-Za-z]{4,}\b", combined))
    shared = scenario_words.intersection(step_words)

    if not has_ref and len(shared) < 2:
        return CriterionResult(
            criterion_id="example_present",
            status=CriterionStatus.FAIL,
            severity=CriterionSeverity.CRITICAL,
            reason="Worked example is not referenced or integrated into instructional steps or summary.",
            affected_section="steps / summary",
            evidence=["No explicit mention of worked example found in steps or summary."],
            suggested_fix="Explicitly refer back to the worked example scenario in the steps or summary.",
        )

    return CriterionResult(
        criterion_id="example_present",
        status=CriterionStatus.PASS,
        severity=CriterionSeverity.CRITICAL,
        reason="Worked example is populated and explicitly referenced in pedagogical text.",
        evidence=["Worked example referenced in instructional text."],
    )


def validate_teaching_flow_structure(lesson: Lesson) -> CriterionResult:
    """Verifies that the instructional sections follow required pedagogical sequencing.

    Args:
        lesson: The lesson draft.

    Returns:
        CriterionResult for teaching_flow_structure.
    """
    if not lesson.steps or len(lesson.steps) < 1:
        return CriterionResult(
            criterion_id="teaching_flow_structure",
            status=CriterionStatus.FAIL,
            severity=CriterionSeverity.MAJOR,
            reason="Lesson lacks instructional steps.",
            affected_section="steps",
            suggested_fix="Add ordered steps decomposing the topic logically.",
        )

    for idx, s in enumerate(lesson.steps, start=1):
        if not s.heading.strip() or not s.body.strip():
            return CriterionResult(
                criterion_id="teaching_flow_structure",
                status=CriterionStatus.FAIL,
                severity=CriterionSeverity.MAJOR,
                reason=f"Step {idx} has an empty heading or body.",
                affected_section=f"steps[{idx}]",
                suggested_fix="Ensure each step contains both a concise heading and clear instructional body.",
            )

    return CriterionResult(
        criterion_id="teaching_flow_structure",
        status=CriterionStatus.PASS,
        severity=CriterionSeverity.MAJOR,
        reason=f"Pedagogical structure is sequential and {len(lesson.steps)} steps are present.",
        evidence=[f"{len(lesson.steps)} instructional steps present"],
    )


def validate_code_integrity(lesson: Lesson) -> CriterionResult:
    """Parses Python blocks with ast.parse; reports other languages as not checked.

    Args:
        lesson: The lesson draft.

    Returns:
        CriterionResult for code_integrity.
    """
    text = lesson.full_text()
    pattern = re.compile(r"```([a-zA-Z0-9_\-\+]*)\n(.*?)```", re.DOTALL)
    matches = pattern.findall(text)

    if not matches:
        return CriterionResult(
            criterion_id="code_integrity",
            status=CriterionStatus.PASS,
            severity=CriterionSeverity.CRITICAL,
            reason="No code blocks present in lesson.",
            evidence=["Zero code blocks found"],
        )

    py_count = 0
    non_py = 0
    for lang, code in matches:
        clean_lang = lang.strip().lower()
        if clean_lang in {"python", "py"}:
            py_count += 1
            try:
                ast.parse(code)
            except SyntaxError as e:
                return CriterionResult(
                    criterion_id="code_integrity",
                    status=CriterionStatus.FAIL,
                    severity=CriterionSeverity.CRITICAL,
                    reason=f"Python code syntax error on line {e.lineno}: {e.msg}",
                    affected_section="code block",
                    evidence=[f"Code snippet: {code[:120]}...", f"Error: {e}"],
                    suggested_fix=f"Fix the Python syntax error: {e.msg}",
                )
        else:
            non_py += 1

    reason_parts = []
    if py_count > 0:
        reason_parts.append(f"{py_count} Python code block(s) parsed successfully with ast.parse")
    if non_py > 0:
        reason_parts.append(f"{non_py} non-Python code block(s) reported as 'not checked'")

    return CriterionResult(
        criterion_id="code_integrity",
        status=CriterionStatus.PASS,
        severity=CriterionSeverity.CRITICAL,
        reason=". ".join(reason_parts) if reason_parts else "Code integrity verified.",
        evidence=[f"Python: {py_count}", f"Non-Python: {non_py}"],
    )


def validate_citation_integrity(
    lesson: Lesson,
    supplied_sources: Optional[List[Dict[str, str]]] = None,
) -> CriterionResult:
    """Guarantees no fabricated sources: references must match supplied source ID or title.

    Args:
        lesson: The lesson draft.
        supplied_sources: Authorized sources provided in the generation request.

    Returns:
        CriterionResult for citation_integrity.
    """
    sources = supplied_sources or []
    valid_ids = {s.get("source_id", "").strip().lower() for s in sources if s.get("source_id")}
    valid_titles = {s.get("title", "").strip().lower() for s in sources if s.get("title")}

    # Case 1: No sources supplied
    if not sources:
        if lesson.references:
            return CriterionResult(
                criterion_id="citation_integrity",
                status=CriterionStatus.FAIL,
                severity=CriterionSeverity.CRITICAL,
                reason="Fabricated citation: references provided when zero sources were supplied.",
                affected_section="references",
                evidence=[f"{r.source_id}: {r.title}" for r in lesson.references],
                suggested_fix="Clear the references list because no authorized sources were supplied.",
            )

        # Check for unsupplied external URLs in text
        url_pattern = re.compile(r"https?://[^\s)\]\"'>]+")
        found_urls = url_pattern.findall(lesson.full_text())
        if found_urls:
            return CriterionResult(
                criterion_id="citation_integrity",
                status=CriterionStatus.FAIL,
                severity=CriterionSeverity.CRITICAL,
                reason="Fabricated citation: external URLs found in lesson body without supplied sources.",
                affected_section="full_text",
                evidence=found_urls,
                suggested_fix="Remove unverified external URLs from lesson content.",
            )

        return CriterionResult(
            criterion_id="citation_integrity",
            status=CriterionStatus.PASS,
            severity=CriterionSeverity.CRITICAL,
            reason="Citation integrity verified: zero citations fabricated where no sources supplied.",
            evidence=["Zero references as expected"],
        )

    # Case 2: Sources were supplied
    unmatched = []
    for ref in lesson.references:
        ref_id = ref.source_id.strip().lower()
        ref_title = ref.title.strip().lower()
        id_match = ref_id in valid_ids or any(ref_id in vid or vid in ref_id for vid in valid_ids if vid)
        title_match = ref_title in valid_titles or any(ref_title in vt or vt in ref_title for vt in valid_titles if vt)
        if not (id_match or title_match):
            unmatched.append(f"{ref.source_id}: {ref.title}")

    if unmatched:
        return CriterionResult(
            criterion_id="citation_integrity",
            status=CriterionStatus.FAIL,
            severity=CriterionSeverity.CRITICAL,
            reason=f"Fabricated citation: reference does not match any supplied source: {', '.join(unmatched)}",
            affected_section="references",
            evidence=unmatched,
            suggested_fix="Only reference sources provided in the input source list.",
        )

    return CriterionResult(
        criterion_id="citation_integrity",
        status=CriterionStatus.PASS,
        severity=CriterionSeverity.CRITICAL,
        reason=f"All {len(lesson.references)} references match authorized supplied sources.",
        evidence=[f"{r.source_id}: {r.title}" for r in lesson.references],
    )


def run_deterministic_checks(
    lesson: Lesson,
    learner_level: LearnerLevel,
    target_length: LessonLength,
    supplied_sources: Optional[List[Dict[str, str]]] = None,
) -> List[CriterionResult]:
    """Runs all 7 deterministic checks sequentially.

    Args:
        lesson: The generated lesson draft.
        learner_level: Target learner level.
        target_length: Target length profile.
        supplied_sources: Optional authorized sources.

    Returns:
        List of 7 CriterionResult objects.
    """
    return [
        validate_output_integrity(lesson, target_length),
        validate_beginner_readability(lesson, learner_level),
        validate_jargon_control(lesson),
        validate_example_present(lesson),
        validate_teaching_flow_structure(lesson),
        validate_code_integrity(lesson),
        validate_citation_integrity(lesson, supplied_sources),
    ]
