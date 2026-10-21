"""Tests for pure deterministic release gate decision logic."""
from evaluation.judge import Claim
from evaluation.validators import CriterionResult, load_rubric_dict
from guardrails.release_gate import release_decision
from shared.enums import (
    ClaimStatus,
    ClaimType,
    CriterionSeverity,
    CriterionStatus,
    EvidenceMode,
)


def get_all_passing_criterion_results():
    rubric = load_rubric_dict()
    results = []
    for r in rubric.get("criteria", []):
        results.append(
            CriterionResult(
                criterion_id=r["id"],
                status=CriterionStatus.PASS,
                severity=CriterionSeverity(r["severity"]),
                reason="Criterion satisfied",
            )
        )
    return results


def test_release_gate_all_pass():
    """All criteria PASS -> approved."""
    results = get_all_passing_criterion_results()
    decision = release_decision(results, claims=[], rubric=load_rubric_dict())
    assert decision.passed is True
    assert len(decision.blocking_failures) == 0


def test_release_gate_missing_criterion_blocks():
    """Missing criterion counts as FAIL and blocks release."""
    results = get_all_passing_criterion_results()
    # Omit factual_accuracy
    results = [r for r in results if r.criterion_id != "factual_accuracy"]
    decision = release_decision(results, claims=[], rubric=load_rubric_dict())
    assert decision.passed is False
    assert "factual_accuracy" in decision.missing_criteria


def test_release_gate_critical_failure_blocks():
    """Failed critical criterion blocks release."""
    results = get_all_passing_criterion_results()
    results[0].status = CriterionStatus.FAIL
    results[0].reason = "Word count out of bounds"
    decision = release_decision(results, claims=[], rubric=load_rubric_dict())
    assert decision.passed is False
    assert len(decision.blocking_failures) > 0


def test_release_gate_provided_docs_contradicted_claim_blocks():
    """In PROVIDED_DOCS mode, a CONTRADICTED material factual claim blocks release."""
    results = get_all_passing_criterion_results()
    claims = [
        Claim(
            id="c-1",
            text="Water splits into helium.",
            type=ClaimType.FACTUAL,
            section="steps",
            material=True,
            status=ClaimStatus.CONTRADICTED,
            source_id="src-1",
        )
    ]
    decision = release_decision(
        criterion_results=results,
        claims=claims,
        evidence_mode=EvidenceMode.PROVIDED_DOCS,
        rubric=load_rubric_dict(),
    )
    assert decision.passed is False
    assert any("CONTRADICTED" in f for f in decision.blocking_failures)


def test_release_gate_provided_docs_partially_supported_does_not_block():
    """In PROVIDED_DOCS mode, a PARTIALLY_SUPPORTED claim is reported only and does NOT block release."""
    results = get_all_passing_criterion_results()
    claims = [
        Claim(
            id="c-1",
            text="Enzymes accelerate reaction speed significantly.",
            type=ClaimType.FACTUAL,
            section="steps",
            material=True,
            status=ClaimStatus.PARTIALLY_SUPPORTED,
            source_id="src-1",
        )
    ]
    decision = release_decision(
        criterion_results=results,
        claims=claims,
        evidence_mode=EvidenceMode.PROVIDED_DOCS,
        rubric=load_rubric_dict(),
    )
    assert decision.passed is True


def test_release_gate_model_knowledge_only_unverifiable_does_not_block():
    """In MODEL_KNOWLEDGE_ONLY mode, UNVERIFIABLE material factual claims do NOT block release."""
    results = get_all_passing_criterion_results()
    claims = [
        Claim(
            id="c-1",
            text="Mitochondria have double membranes.",
            type=ClaimType.FACTUAL,
            section="steps",
            material=True,
            status=ClaimStatus.UNVERIFIABLE,
        )
    ]
    decision = release_decision(
        criterion_results=results,
        claims=claims,
        evidence_mode=EvidenceMode.MODEL_KNOWLEDGE_ONLY,
        rubric=load_rubric_dict(),
    )
    assert decision.passed is True
