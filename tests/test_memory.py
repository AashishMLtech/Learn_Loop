"""Unit and Integration Tests for Memory, Persistence, and Proposals Management.

Purpose:
    Tests persistence round-trips for runs, versions, evaluations, rejection logs,
    token usage, and feedback. Verifies Level A static pitfall hints aggregation and
    Level B proposal lifecycle (evaluation, admin-gated approval, rollback).

Inputs/Outputs:
    Inputs: SQLAlchemy sessions, mock runs, rejection logs, proposal models.
    Outputs: Assertions on database state and CLI proposal management behaviors.

What it must NOT do:
    - Must NOT hardcode demo topic terms.
    - Must NOT bypass admin authorization requirements for proposal approval.
"""
import os
import uuid

import pytest

from memory.store import (
    STATIC_PITFALL_TEMPLATES,
    EvaluationModel,
    FeedbackModel,
    LessonVersionModel,
    ProposalModel,
    RejectionLogModel,
    RunModel,
    TokenUsageModel,
    get_common_pitfalls_hint,
    get_db_context,
    init_db,
    recover_stale_running_runs,
)
from scripts.manage_proposals import approve_proposal, evaluate_proposal, list_proposals, rollback_proposal
from shared.enums import CriterionSeverity, CriterionStatus, ProposalStatus, RetryResult, RunStatus


def setup_module() -> None:
    """Initializes tables before running memory tests."""
    init_db()


def test_models_persistence_and_roundtrip() -> None:
    """Verifies all core models persist and correctly round-trip via SQLAlchemy."""
    run_id = f"test-run-{uuid.uuid4()}"
    version_id = f"test-ver-{uuid.uuid4()}"

    with get_db_context() as db:
        run = RunModel(
            id=run_id,
            topic="Operating Systems Virtual Memory",
            learner_level="beginner",
            objectives=["Understand page tables", "Learn TLB purpose"],
            target_length="medium",
            max_retries=2,
            status=RunStatus.RUNNING.value,
        )
        db.add(run)

        version = LessonVersionModel(
            id=version_id,
            run_id=run_id,
            version_number=1,
            content={"title": "Virtual Memory Basics", "introduction": "Virtual memory abstracts physical RAM."},
            changes_made=["Initial generation"],
        )
        db.add(version)

        eval_model = EvaluationModel(
            id=f"eval-{uuid.uuid4()}",
            run_id=run_id,
            lesson_version_id=version_id,
            rubric_version="1.0.0",
            judge_model="mock-judge-v1",
            criterion_results=[
                {
                    "criterion_id": "output_integrity",
                    "status": CriterionStatus.PASS.value,
                    "severity": CriterionSeverity.CRITICAL.value,
                    "blocking": True,
                    "reason": "Valid",
                }
            ],
            claims=[],
            passed=True,
        )
        db.add(eval_model)

        rej_model = RejectionLogModel(
            id=f"rej-{uuid.uuid4()}",
            run_id=run_id,
            attempt=1,
            failed_criteria=["jargon_control"],
            reasons=["Undefined term: paging"],
            changes_made=["Added glossary entry"],
            result=RetryResult.RETRYING.value,
        )
        db.add(rej_model)

        tok_model = TokenUsageModel(
            id=f"tok-{uuid.uuid4()}",
            run_id=run_id,
            attempt=1,
            call_type="generate",
            model="mock-gen-v1",
            prompt_tokens=400,
            completion_tokens=250,
            total_tokens=650,
            is_estimated=False,
        )
        db.add(tok_model)

        fb_model = FeedbackModel(
            id=f"fb-{uuid.uuid4()}",
            run_id=run_id,
            rating=5,
            issue_tags=["clear_examples"],
            comment="Great clear walkthrough.",
        )
        db.add(fb_model)

    # Verify retrieval
    with get_db_context() as db:
        loaded_run = db.get(RunModel, run_id)
        assert loaded_run is not None
        assert loaded_run.topic == "Operating Systems Virtual Memory"
        assert len(loaded_run.versions) == 1
        assert loaded_run.versions[0].id == version_id
        assert len(loaded_run.evaluations) == 1
        assert loaded_run.evaluations[0].passed is True
        assert len(loaded_run.rejection_logs) == 1
        assert loaded_run.rejection_logs[0].failed_criteria == ["jargon_control"]
        assert len(loaded_run.tokens) == 1
        assert loaded_run.tokens[0].total_tokens == 650
        assert len(loaded_run.feedbacks) == 1
        assert loaded_run.feedbacks[0].rating == 5


def test_level_a_pitfall_hints_aggregation_and_token_cap() -> None:
    """Verifies aggregation of top-3 failing criteria and enforcement of static templates."""
    with get_db_context() as db:
        # Seed several rejection records with known failures
        for _ in range(5):
            db.add(
                RejectionLogModel(
                    id=f"rej-{uuid.uuid4()}",
                    run_id=f"run-{uuid.uuid4()}",
                    attempt=1,
                    failed_criteria=["jargon_control", "beginner_readability"],
                    reasons=["Flesch grade high"],
                    changes_made=[],
                    result=RetryResult.RETRYING.value,
                )
            )
        for _ in range(3):
            db.add(
                RejectionLogModel(
                    id=f"rej-{uuid.uuid4()}",
                    run_id=f"run-{uuid.uuid4()}",
                    attempt=1,
                    failed_criteria=["jargon_control", "output_integrity"],
                    reasons=["Word count off"],
                    changes_made=[],
                    result=RetryResult.RETRYING.value,
                )
            )

    with get_db_context() as db:
        hint_text, hint_ver = get_common_pitfalls_hint(db, limit_runs=50, token_cap=150)
        assert hint_text != ""
        assert "jargon_control" in hint_ver
        # Confirm static template is used verbatim
        assert STATIC_PITFALL_TEMPLATES["jargon_control"] in hint_text
        # Enforce that words count is well within the 150 token ceiling
        assert len(hint_text.split()) <= 100


def test_recover_stale_running_runs() -> None:
    """Verifies that runs left in RUNNING status are recovered to ERROR on restart."""
    stale_id = f"stale-{uuid.uuid4()}"
    with get_db_context() as db:
        db.add(
            RunModel(
                id=stale_id,
                topic="Sorting Algorithms",
                learner_level="beginner",
                objectives=["Bubble sort"],
                target_length="short",
                max_retries=1,
                status=RunStatus.RUNNING.value,
            )
        )

    count = recover_stale_running_runs()
    assert count >= 1

    with get_db_context() as db:
        recovered = db.get(RunModel, stale_id)
        assert recovered is not None
        assert recovered.status == RunStatus.ERROR.value
        assert "Server restarted" in (recovered.error_message or "")


def test_level_b_proposals_lifecycle(capsys: pytest.CaptureFixture) -> None:
    """Verifies Level B proposal listing, golden evaluation, admin approval, and rollback."""
    prop_id = f"prop-{uuid.uuid4()}"
    os.environ["ADMIN_API_KEY"] = "test-secret-key-123"

    with get_db_context() as db:
        db.add(
            ProposalModel(
                id=prop_id,
                target="prompt_guidance:beginner_readability",
                rationale="Elevated grade levels observed across scientific topics.",
                evidence={"historical_failure_rate": 0.28},
                proposed_change="Explicitly request active voice and short clauses.",
                status=ProposalStatus.PROPOSED.value,
            )
        )

    # 1. Test list proposals
    list_proposals()
    captured = capsys.readouterr()
    assert prop_id in captured.out

    # 2. Test evaluate proposal
    evaluate_proposal(prop_id)
    captured = capsys.readouterr()
    assert "Evaluating Proposal" in captured.out

    # 3. Test approval with invalid key -> should fail with SystemExit
    with pytest.raises(SystemExit):
        approve_proposal(prop_id, admin_key="wrong-key")

    # 4. Test approval with valid key
    approve_proposal(prop_id, admin_key="test-secret-key-123", actor="qa_lead", reason="Verified")
    captured = capsys.readouterr()
    assert "approved and marked ACTIVE" in captured.out

    with get_db_context() as db:
        p_active = db.get(ProposalModel, prop_id)
        assert p_active is not None
        assert p_active.status == ProposalStatus.ACTIVE.value
        assert p_active.approved_by == "qa_lead"

    # 5. Test rollback with valid key
    rollback_proposal(prop_id, admin_key="test-secret-key-123")
    captured = capsys.readouterr()
    assert "rolled back" in captured.out

    with get_db_context() as db:
        p_rolled = db.get(ProposalModel, prop_id)
        assert p_rolled is not None
        assert p_rolled.status == ProposalStatus.ROLLED_BACK.value
