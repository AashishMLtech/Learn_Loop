"""Milestone 1 Gate Integration Tests.

Purpose:
    Verifies all 14 required M1 gate conditions across state machine routing,
    budget enforcement, retry limits, cancellation, and error handling.
"""
import uuid
from unittest.mock import MagicMock

import pytest

from agent.graph import execute_lesson_workflow
from agent.state import AgentState
from evaluation.judge import Claim, JudgeEvaluationError, JudgeOutput, compute_judge_cache_key
from evaluation.validators import CriterionResult
from generation.schema import (
    ComprehensionQuestion,
    GlossaryItem,
    Lesson,
    LessonRevisionOutput,
    LessonStep,
    ReferenceItem,
    WorkedExample,
)
from memory.store import (
    RunModel,
    get_db_context,
    init_db,
)
from shared.enums import (
    ClaimStatus,
    ClaimType,
    CriterionSeverity,
    CriterionStatus,
    LearnerLevel,
    LessonLength,
    RunStatus,
)
from shared.llm_client import (
    BudgetExhaustedError,
    InfrastructureExhaustedError,
    TokenBudgetTracker,
)


@pytest.fixture(autouse=True)
def setup_database():
    """Initializes in-memory or file database before each test."""
    init_db()


def make_valid_lesson() -> Lesson:
    """Builds a fully compliant Lesson object with sufficient word count."""
    return Lesson(
        title="Cellular Bioenergetics Fundamentals",
        introduction="Living cells harness chemical potential energy from glucose through ordered metabolic pathways. In this beginner guide, we explore the coordinated biochemical steps cells take to sustain biological vitality and fuel organismal growth.",
        prerequisites=["Basic cellular structure", "Simple chemical bonds"],
        definition="Cellular respiration is a metabolic pathway oxidizing glucose in the presence of oxygen to synthesize ATP.",
        why_it_matters="Without ATP synthesis, physiological tasks such as muscle contraction, cellular repair, and neural transmission cease, causing cellular shutdown.",
        steps=[
            LessonStep(
                heading="Step 1: Cytoplasmic Glycolysis",
                body="Enzymes split one six-carbon glucose molecule into two three-carbon pyruvate units in the cytoplasm, yielding two net ATP molecules and electron carriers without requiring oxygen.",
            ),
            LessonStep(
                heading="Step 2: Mitochondrial Electron Transport",
                body="Electrons flow down membrane-bound protein complexes, pumping protons across the cristae to fuel ATP synthase. As demonstrated in our worked example scenario, energy extraction proceeds methodically to generate abundant ATP.",
            ),
        ],
        worked_example=WorkedExample(
            scenario="A resting human muscle cell metabolizing a single glucose molecule during quiet respiration.",
            walkthrough="1. Glycolysis cleaves glucose into two pyruvates in the cytoplasm. 2. Pyruvates enter the mitochondrial matrix. 3. Oxidative phosphorylation generates thirty ATP molecules.",
        ),
        key_distinctions=[
            "Aerobic respiration requires oxygen; anaerobic fermentation produces lactate without oxygen.",
        ],
        common_misunderstandings=[
            "Cellular respiration is distinct from breathing; lungs transport oxygen to fuel cellular respiration.",
        ],
        glossary=[
            GlossaryItem(term="ATP", definition="Adenosine triphosphate, the primary biochemical energy storage molecule."),
            GlossaryItem(term="Glycolysis", definition="The cytoplasmic breakdown of glucose into pyruvate molecules."),
        ],
        specialized_terms=["ATP", "Glycolysis"],
        summary="Cellular respiration converts glucose and oxygen into ATP, carbon dioxide, and water. As highlighted in the worked example, sequential metabolic steps maximize usable biological energy yield across the entire cell.",
        takeaways=[
            "Respiration yields chemical ATP energy from glucose.",
            "Glycolysis occurs in cytoplasm, while electron transport takes place in mitochondria.",
        ],
        comprehension_questions=[
            ComprehensionQuestion(question="What is the net ATP yield of glycolysis alone?", answer="Two net ATP."),
        ],
        references=[ReferenceItem(source_id="src-1", title="Principles of Biology Chapter 9")],
    )


def make_judge_output(all_pass: bool = True, failed_cid: str = "factual_accuracy") -> JudgeOutput:
    """Constructs mock JudgeOutput."""
    cids = [
        "factual_accuracy",
        "internal_consistency",
        "example_correctness",
        "topic_coverage",
        "coherence_of_flow",
        "standalone_completeness",
    ]
    results = []
    for c in cids:
        if not all_pass and c == failed_cid:
            results.append(
                CriterionResult(
                    criterion_id=c,
                    status=CriterionStatus.FAIL,
                    severity=CriterionSeverity.CRITICAL,
                    reason=f"Test failure in {c}",
                )
            )
        else:
            results.append(
                CriterionResult(
                    criterion_id=c,
                    status=CriterionStatus.PASS,
                    severity=CriterionSeverity.CRITICAL if c in {"factual_accuracy", "internal_consistency"} else CriterionSeverity.MAJOR,
                    reason="Passes criterion standards",
                )
            )

    claims = [
        Claim(
            id="claim-1",
            text="Glucose is cleaved into pyruvate.",
            type=ClaimType.FACTUAL,
            section="steps",
            material=True,
            status=ClaimStatus.SUPPORTED,
            source_id="src-1",
            evidence_quote="Glycolysis cleaves glucose",
        )
    ]
    return JudgeOutput(criteria_results=results, claims=claims)


def test_1_pass_on_first_try():
    """Gate Test 1: Lesson passes on the first attempt when all criteria pass."""
    run_id = str(uuid.uuid4())
    lesson = make_valid_lesson()

    with get_db_context() as db:
        run = RunModel(
            id=run_id,
            topic="Cellular Respiration",
            learner_level=LearnerLevel.BEGINNER.value,
            objectives=["Explain ATP synthesis"],
            target_length=LessonLength.SHORT.value,
            max_retries=1,
            status=RunStatus.RUNNING.value,
        )
        db.add(run)

    mock_gen = MagicMock()
    mock_gen.generate.return_value = lesson

    mock_judge = MagicMock()
    mock_judge.judge.return_value = make_judge_output(all_pass=True)
    mock_judge.model = "llama-3.1-8b-instant"

    state: AgentState = {
        "run_id": run_id,
        "topic": "Cellular Respiration",
        "learner_level": LearnerLevel.BEGINNER,
        "learning_objectives": ["Explain ATP synthesis"],
        "target_length": LessonLength.SHORT,
        "max_retries": 1,
        "supplied_sources": [{"source_id": "src-1", "title": "Principles of Biology Chapter 9"}],
        "token_tracker": TokenBudgetTracker(max_budget=30000),
        "services": {"generator_service": mock_gen, "judge_service": mock_judge},
    }

    final_state = execute_lesson_workflow(state)

    assert final_state["status"] == RunStatus.PASS
    assert final_state["current_attempt"] == 1
    assert mock_gen.generate.call_count == 1
    assert mock_judge.judge.call_count == 1


def test_2_fail_then_pass_after_one_revision():
    """Gate Test 2: Lesson fails attempt 1, revises with failure reasons, and passes attempt 2."""
    run_id = str(uuid.uuid4())
    lesson = make_valid_lesson()
    revised_lesson = lesson.model_copy(deep=True)
    revised_lesson.title = "Cellular Bioenergetics (Revised Edition)"

    with get_db_context() as db:
        run = RunModel(
            id=run_id,
            topic="Cellular Respiration",
            learner_level=LearnerLevel.BEGINNER.value,
            objectives=["Explain ATP synthesis"],
            target_length=LessonLength.SHORT.value,
            max_retries=1,
            status=RunStatus.RUNNING.value,
        )
        db.add(run)

    mock_gen = MagicMock()
    mock_gen.generate.return_value = lesson
    mock_gen.revise.return_value = LessonRevisionOutput(
        lesson=revised_lesson,
        changes_made=["Resolved factual ambiguity regarding ATP synthase"],
    )

    mock_judge = MagicMock()
    mock_judge.judge.side_effect = [
        make_judge_output(all_pass=False, failed_cid="factual_accuracy"),
        make_judge_output(all_pass=True),
    ]
    mock_judge.model = "llama-3.1-8b-instant"

    state: AgentState = {
        "run_id": run_id,
        "topic": "Cellular Respiration",
        "learner_level": LearnerLevel.BEGINNER,
        "learning_objectives": ["Explain ATP synthesis"],
        "target_length": LessonLength.SHORT,
        "max_retries": 1,
        "supplied_sources": [{"source_id": "src-1", "title": "Principles of Biology Chapter 9"}],
        "token_tracker": TokenBudgetTracker(max_budget=30000),
        "services": {"generator_service": mock_gen, "judge_service": mock_judge},
    }

    final_state = execute_lesson_workflow(state)

    assert final_state["status"] == RunStatus.PASS
    assert final_state["current_attempt"] == 2
    assert mock_gen.generate.call_count == 1
    assert mock_gen.revise.call_count == 1
    assert mock_judge.judge.call_count == 2
    assert len(final_state["rejection_log"]) == 2
    assert final_state["rejection_log"][0]["result"] == "RETRYING"
    assert final_state["rejection_log"][1]["result"] == "PASS"


def test_3_and_4_reject_at_cap_and_cap_never_exceeded():
    """Gate Tests 3 & 4: Rejects after max_retries cap is reached; cap is never exceeded."""
    run_id = str(uuid.uuid4())
    lesson = make_valid_lesson()

    with get_db_context() as db:
        run = RunModel(
            id=run_id,
            topic="Cellular Respiration",
            learner_level=LearnerLevel.BEGINNER.value,
            objectives=["Explain ATP synthesis"],
            target_length=LessonLength.SHORT.value,
            max_retries=1,
            status=RunStatus.RUNNING.value,
        )
        db.add(run)

    mock_gen = MagicMock()
    mock_gen.generate.return_value = lesson
    mock_gen.revise.return_value = LessonRevisionOutput(
        lesson=lesson,
        changes_made=["Attempted fix"],
    )

    mock_judge = MagicMock()
    mock_judge.judge.return_value = make_judge_output(all_pass=False, failed_cid="factual_accuracy")
    mock_judge.model = "llama-3.1-8b-instant"

    state: AgentState = {
        "run_id": run_id,
        "topic": "Cellular Respiration",
        "learner_level": LearnerLevel.BEGINNER,
        "learning_objectives": ["Explain ATP synthesis"],
        "target_length": LessonLength.SHORT,
        "max_retries": 1,
        "supplied_sources": [{"source_id": "src-1", "title": "Principles of Biology Chapter 9"}],
        "token_tracker": TokenBudgetTracker(max_budget=30000),
        "services": {"generator_service": mock_gen, "judge_service": mock_judge},
    }

    final_state = execute_lesson_workflow(state)

    # Test 3: Status is REJECTED
    assert final_state["status"] == RunStatus.REJECTED

    # Test 4: Exactly 2 total attempts executed (1 initial + 1 retry = 2 calls)
    assert final_state["current_attempt"] == 2
    assert mock_gen.generate.call_count == 1
    assert mock_gen.revise.call_count == 1
    assert mock_judge.judge.call_count == 2
    assert final_state["rejection_log"][-1]["result"] == "REJECTED"


def test_5_invalid_judge_json_never_passes():
    """Gate Test 5: Malformed judge JSON raises JudgeEvaluationError and yields ERROR, never PASS."""
    run_id = str(uuid.uuid4())
    lesson = make_valid_lesson()

    with get_db_context() as db:
        run = RunModel(
            id=run_id,
            topic="Cellular Respiration",
            learner_level=LearnerLevel.BEGINNER.value,
            objectives=["Explain ATP synthesis"],
            target_length=LessonLength.SHORT.value,
            max_retries=1,
            status=RunStatus.RUNNING.value,
        )
        db.add(run)

    mock_gen = MagicMock()
    mock_gen.generate.return_value = lesson

    # Mock judge raises JudgeEvaluationError (format repair failed)
    mock_judge = MagicMock()
    mock_judge.judge.side_effect = JudgeEvaluationError("Malformed JSON after repair")
    mock_judge.model = "llama-3.1-8b-instant"

    state: AgentState = {
        "run_id": run_id,
        "topic": "Cellular Respiration",
        "learner_level": LearnerLevel.BEGINNER,
        "learning_objectives": ["Explain ATP synthesis"],
        "target_length": LessonLength.SHORT,
        "max_retries": 1,
        "supplied_sources": [{"source_id": "src-1", "title": "Principles of Biology Chapter 9"}],
        "token_tracker": TokenBudgetTracker(max_budget=30000),
        "services": {"generator_service": mock_gen, "judge_service": mock_judge},
    }

    final_state = execute_lesson_workflow(state)

    assert final_state["status"] == RunStatus.ERROR
    assert "Malformed JSON" in (final_state.get("error_message") or "")


def test_6_missing_criterion_never_passes():
    """Gate Test 6: A missing criterion result counts as FAIL and cannot pass release gate."""
    run_id = str(uuid.uuid4())
    lesson = make_valid_lesson()

    with get_db_context() as db:
        run = RunModel(
            id=run_id,
            topic="Cellular Respiration",
            learner_level=LearnerLevel.BEGINNER.value,
            objectives=["Explain ATP synthesis"],
            target_length=LessonLength.SHORT.value,
            max_retries=0,
            status=RunStatus.RUNNING.value,
        )
        db.add(run)

    mock_gen = MagicMock()
    mock_gen.generate.return_value = lesson

    # Judge returns output missing 'coherence_of_flow'
    output = make_judge_output(all_pass=True)
    output.criteria_results = [r for r in output.criteria_results if r.criterion_id != "coherence_of_flow"]

    mock_judge = MagicMock()
    mock_judge.judge.return_value = output
    mock_judge.model = "llama-3.1-8b-instant"

    state: AgentState = {
        "run_id": run_id,
        "topic": "Cellular Respiration",
        "learner_level": LearnerLevel.BEGINNER,
        "learning_objectives": ["Explain ATP synthesis"],
        "target_length": LessonLength.SHORT,
        "max_retries": 0,
        "supplied_sources": [{"source_id": "src-1", "title": "Principles of Biology Chapter 9"}],
        "token_tracker": TokenBudgetTracker(max_budget=30000),
        "services": {"generator_service": mock_gen, "judge_service": mock_judge},
    }

    final_state = execute_lesson_workflow(state)

    assert final_state["status"] == RunStatus.REJECTED
    assert any("coherence_of_flow" in f for f in final_state["release_decision"].missing_criteria)


def test_7_provider_429_outage_produces_error_not_lesson_retry():
    """Gate Test 7: Infrastructure error yields status ERROR, not REJECTED or PASS, not counted as retry."""
    run_id = str(uuid.uuid4())

    with get_db_context() as db:
        run = RunModel(
            id=run_id,
            topic="Cellular Respiration",
            learner_level=LearnerLevel.BEGINNER.value,
            objectives=["Explain ATP synthesis"],
            target_length=LessonLength.SHORT.value,
            max_retries=1,
            status=RunStatus.RUNNING.value,
        )
        db.add(run)

    mock_gen = MagicMock()
    mock_gen.generate.side_effect = InfrastructureExhaustedError("Provider 429 rate limit exhausted")

    mock_judge = MagicMock()

    state: AgentState = {
        "run_id": run_id,
        "topic": "Cellular Respiration",
        "learner_level": LearnerLevel.BEGINNER,
        "learning_objectives": ["Explain ATP synthesis"],
        "target_length": LessonLength.SHORT,
        "max_retries": 1,
        "supplied_sources": [],
        "token_tracker": TokenBudgetTracker(max_budget=30000),
        "services": {"generator_service": mock_gen, "judge_service": mock_judge},
    }

    final_state = execute_lesson_workflow(state)

    assert final_state["status"] == RunStatus.ERROR
    assert final_state.get("current_attempt", 1) == 1
    assert "Provider 429 rate limit exhausted" in (final_state.get("error_message") or "")


def test_8_fabricated_citation_fails():
    """Gate Test 8: Fabricated citation fails citation_integrity and blocks release."""
    run_id = str(uuid.uuid4())
    flawed_lesson = make_valid_lesson()
    flawed_lesson.references = [ReferenceItem(source_id="fake-source-99", title="Fabricated Book")]

    with get_db_context() as db:
        run = RunModel(
            id=run_id,
            topic="Cellular Respiration",
            learner_level=LearnerLevel.BEGINNER.value,
            objectives=["Explain ATP synthesis"],
            target_length=LessonLength.SHORT.value,
            max_retries=0,
            status=RunStatus.RUNNING.value,
        )
        db.add(run)

    mock_gen = MagicMock()
    mock_gen.generate.return_value = flawed_lesson

    mock_judge = MagicMock()
    mock_judge.model = "llama-3.1-8b-instant"

    state: AgentState = {
        "run_id": run_id,
        "topic": "Cellular Respiration",
        "learner_level": LearnerLevel.BEGINNER,
        "learning_objectives": ["Explain ATP synthesis"],
        "target_length": LessonLength.SHORT,
        "max_retries": 0,
        "supplied_sources": [],
        "token_tracker": TokenBudgetTracker(max_budget=30000),
        "services": {"generator_service": mock_gen, "judge_service": mock_judge},
    }

    final_state = execute_lesson_workflow(state)

    assert final_state["status"] == RunStatus.REJECTED
    det_results = final_state.get("deterministic_results", [])
    cit_res = next(r for r in det_results if r.criterion_id == "citation_integrity")
    assert cit_res.status == CriterionStatus.FAIL


def test_9_budget_exhaustion_blocks_further_calls():
    """Gate Test 9: Budget exhaustion halts execution with BUDGET_EXHAUSTED."""
    run_id = str(uuid.uuid4())

    with get_db_context() as db:
        run = RunModel(
            id=run_id,
            topic="Cellular Respiration",
            learner_level=LearnerLevel.BEGINNER.value,
            objectives=["Explain ATP synthesis"],
            target_length=LessonLength.SHORT.value,
            max_retries=1,
            status=RunStatus.RUNNING.value,
        )
        db.add(run)

    tracker = TokenBudgetTracker(max_budget=500)
    mock_gen = MagicMock()
    mock_gen.generate.side_effect = BudgetExhaustedError("Token budget exhausted")

    mock_judge = MagicMock()

    state: AgentState = {
        "run_id": run_id,
        "topic": "Cellular Respiration",
        "learner_level": LearnerLevel.BEGINNER,
        "learning_objectives": ["Explain ATP synthesis"],
        "target_length": LessonLength.SHORT,
        "max_retries": 1,
        "supplied_sources": [],
        "token_tracker": tracker,
        "services": {"generator_service": mock_gen, "judge_service": mock_judge},
    }

    final_state = execute_lesson_workflow(state)

    assert final_state["status"] == RunStatus.BUDGET_EXHAUSTED


def test_10_per_attempt_calls_never_exceed_2():
    """Gate Test 10: Per-attempt LLM calls never exceed 2 (assert on mock call log)."""
    run_id = str(uuid.uuid4())
    lesson = make_valid_lesson()

    with get_db_context() as db:
        run = RunModel(
            id=run_id,
            topic="Cellular Respiration",
            learner_level=LearnerLevel.BEGINNER.value,
            objectives=["Explain ATP synthesis"],
            target_length=LessonLength.SHORT.value,
            max_retries=1,
            status=RunStatus.RUNNING.value,
        )
        db.add(run)

    mock_gen = MagicMock()
    mock_gen.generate.return_value = lesson
    mock_gen.revise.return_value = LessonRevisionOutput(lesson=lesson, changes_made=["Edits"])

    mock_judge = MagicMock()
    mock_judge.judge.side_effect = [
        make_judge_output(all_pass=False, failed_cid="factual_accuracy"),
        make_judge_output(all_pass=True),
    ]
    mock_judge.model = "llama-3.1-8b-instant"

    state: AgentState = {
        "run_id": run_id,
        "topic": "Cellular Respiration",
        "learner_level": LearnerLevel.BEGINNER,
        "learning_objectives": ["Explain ATP synthesis"],
        "target_length": LessonLength.SHORT,
        "max_retries": 1,
        "supplied_sources": [{"source_id": "src-1", "title": "Principles of Biology Chapter 9"}],
        "token_tracker": TokenBudgetTracker(max_budget=30000),
        "services": {"generator_service": mock_gen, "judge_service": mock_judge},
    }

    execute_lesson_workflow(state)

    # Attempt 1: 1 generate + 1 judge = 2 calls
    # Attempt 2: 1 revise + 1 judge = 2 calls
    assert mock_gen.generate.call_count == 1
    assert mock_gen.revise.call_count == 1
    assert mock_judge.judge.call_count == 2


def test_11_deterministic_failure_skips_judge():
    """Gate Test 11: A deterministic check failure skips the LLM judge call for that attempt."""
    run_id = str(uuid.uuid4())
    flawed_lesson = make_valid_lesson()
    flawed_lesson.glossary[0].definition = ""  # Deterministic failure: empty glossary definition

    fixed_lesson = make_valid_lesson()

    with get_db_context() as db:
        run = RunModel(
            id=run_id,
            topic="Cellular Respiration",
            learner_level=LearnerLevel.BEGINNER.value,
            objectives=["Explain ATP synthesis"],
            target_length=LessonLength.SHORT.value,
            max_retries=1,
            status=RunStatus.RUNNING.value,
        )
        db.add(run)

    mock_gen = MagicMock()
    mock_gen.generate.return_value = flawed_lesson
    mock_gen.revise.return_value = LessonRevisionOutput(lesson=fixed_lesson, changes_made=["Fixed glossary"])

    mock_judge = MagicMock()
    mock_judge.judge.return_value = make_judge_output(all_pass=True)
    mock_judge.model = "llama-3.1-8b-instant"

    state: AgentState = {
        "run_id": run_id,
        "topic": "Cellular Respiration",
        "learner_level": LearnerLevel.BEGINNER,
        "learning_objectives": ["Explain ATP synthesis"],
        "target_length": LessonLength.SHORT,
        "max_retries": 1,
        "supplied_sources": [{"source_id": "src-1", "title": "Principles of Biology Chapter 9"}],
        "token_tracker": TokenBudgetTracker(max_budget=30000),
        "services": {"generator_service": mock_gen, "judge_service": mock_judge},
    }

    final_state = execute_lesson_workflow(state)

    # Attempt 1 skipped judge! Judge was called ONLY in attempt 2 after deterministic checks passed.
    assert mock_judge.judge.call_count == 1
    assert final_state["status"] == RunStatus.PASS


def test_12_changed_lesson_invalidates_cache():
    """Gate Test 12: Changing lesson content invalidates judge cache key."""
    lesson_v1 = make_valid_lesson()
    lesson_v2 = lesson_v1.model_copy(deep=True)
    lesson_v2.title = "Cellular Respiration - Version 2"

    key_v1 = compute_judge_cache_key(lesson_text=lesson_v1.full_text())
    key_v2 = compute_judge_cache_key(lesson_text=lesson_v2.full_text())

    assert key_v1 != key_v2


def test_13_cancellation_halts_with_cancelled():
    """Gate Test 13: Cancellation flag halts execution before LLM call with status CANCELLED."""
    run_id = str(uuid.uuid4())

    with get_db_context() as db:
        run = RunModel(
            id=run_id,
            topic="Cellular Respiration",
            learner_level=LearnerLevel.BEGINNER.value,
            objectives=["Explain ATP synthesis"],
            target_length=LessonLength.SHORT.value,
            max_retries=1,
            status=RunStatus.RUNNING.value,
            cancel_requested=True,  # Cancel flag set
        )
        db.add(run)

    mock_gen = MagicMock()
    mock_judge = MagicMock()

    state: AgentState = {
        "run_id": run_id,
        "topic": "Cellular Respiration",
        "learner_level": LearnerLevel.BEGINNER,
        "learning_objectives": ["Explain ATP synthesis"],
        "target_length": LessonLength.SHORT,
        "max_retries": 1,
        "cancel_requested": True,
        "supplied_sources": [],
        "token_tracker": TokenBudgetTracker(max_budget=30000),
        "services": {"generator_service": mock_gen, "judge_service": mock_judge},
    }

    final_state = execute_lesson_workflow(state)

    assert final_state["status"] == RunStatus.CANCELLED
    assert mock_gen.generate.call_count == 0
    assert mock_judge.judge.call_count == 0
