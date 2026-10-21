

"""Deterministic Release Gate Module.

Purpose:
    Enforces pure deterministic release decision making. Evaluates criterion results,
    claim grounding statuses, evidence mode, and rubric specifications.

Inputs/Outputs:
    Inputs: criterion_results, claims, evidence_mode, rubric.
    Outputs: ReleaseDecision containing boolean verdict and explanatory reasons.

What it must NOT do:
    - Must NOT import anything other than enums.
    - Must NOT make network calls, access databases, or mutate inputs.
    - Must NOT be overridden by UI, judge, or generator.

Truth Table:
+------------------------------------+----------------------+----------------+
| Condition                          | Evidence Mode        | Release Verdict|
+------------------------------------+----------------------+----------------+
| Any missing rubric criterion       | Any                  | BLOCKED (FAIL) |
| Any blocking criterion != PASS     | Any                  | BLOCKED (FAIL) |
| Any critical criterion != PASS     | Any                  | BLOCKED (FAIL) |
| Citation integrity != PASS         | Any                  | BLOCKED (FAIL) |
| Material claim CONTRADICTED        | PROVIDED_DOCS        | BLOCKED (FAIL) |
| Material claim UNSUPPORTED         | PROVIDED_DOCS        | BLOCKED (FAIL) |
| Material claim PARTIALLY_SUPPORTED | PROVIDED_DOCS        | APPROVED (PASS)|
| Material claim UNVERIFIABLE        | MODEL_KNOWLEDGE_ONLY | APPROVED (PASS)|
| All blocking criteria PASS & valid | Any                  | APPROVED (PASS)|
+------------------------------------+----------------------+----------------+
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from shared.enums import (
    ClaimStatus,
    ClaimType,
    CriterionSeverity,
    CriterionStatus,
    EvidenceMode,
)


@dataclass(frozen=True)
class ReleaseDecision:
    """Immutable release verdict and detailed reasoning."""
    passed: bool
    reasons: List[str] = field(default_factory=list)
    blocking_failures: List[str] = field(default_factory=list)
    missing_criteria: List[str] = field(default_factory=list)
    unsupported_claims: List[str] = field(default_factory=list)


def release_decision(
    criterion_results: List[Any],
    claims: Optional[List[Any]] = None,
    evidence_mode: EvidenceMode = EvidenceMode.MODEL_KNOWLEDGE_ONLY,
    rubric: Optional[Dict[str, Any]] = None,
) -> ReleaseDecision:
    """Evaluates release gate rules as a pure mathematical decision function.

    Args:
        criterion_results: List of objects or dicts with criterion_id, status, severity.
        claims: Optional list of objects or dicts with material, type, status.
        evidence_mode: Operating mode (MODEL_KNOWLEDGE_ONLY or PROVIDED_DOCS).
        rubric: Rubric specification dictionary containing criteria list.

    Returns:
        ReleaseDecision object with passed boolean and reasons.
    """
    rubric_dict = rubric or {}
    rubric_criteria = rubric_dict.get("criteria", [])

    results_map: Dict[str, Any] = {}
    for cr in criterion_results:
        cid = getattr(cr, "criterion_id", None) or (cr.get("criterion_id") if isinstance(cr, dict) else None)
        if cid:
            results_map[cid] = cr

    blocking_failures: List[str] = []
    missing_criteria: List[str] = []
    reasons: List[str] = []

    # 1. Audit against rubric criteria definitions
    for rule in rubric_criteria:
        cid = rule.get("id")
        is_blocking = rule.get("blocking", True)
        rule_severity = rule.get("severity", "major")

        if cid not in results_map:
            missing_criteria.append(cid)
            blocking_failures.append(f"Missing required criterion result: {cid}")
            continue

        res = results_map[cid]
        status = getattr(res, "status", None) or (res.get("status") if isinstance(res, dict) else None)
        severity = getattr(res, "severity", None) or (res.get("severity") if isinstance(res, dict) else rule_severity)
        reason_text = getattr(res, "reason", "") or (res.get("reason", "") if isinstance(res, dict) else "")

        if isinstance(status, str):
            status = CriterionStatus(status)
        if isinstance(severity, str):
            severity = CriterionSeverity(severity)

        if status != CriterionStatus.PASS:
            sev_val = severity.value if isinstance(severity, CriterionSeverity) else str(severity or "major")
            detail = f"{cid} ({sev_val}): {reason_text or 'Evaluation failed'}"
            if is_blocking or severity == CriterionSeverity.CRITICAL:
                blocking_failures.append(detail)
            reasons.append(detail)

    # 2. Audit material claims based on evidence mode
    unsupported_claims: List[str] = []
    if claims and evidence_mode == EvidenceMode.PROVIDED_DOCS:
        for c in claims:
            is_material = getattr(c, "material", True) if hasattr(c, "material") else c.get("material", True)
            c_type = getattr(c, "type", ClaimType.FACTUAL) if hasattr(c, "type") else c.get("type", ClaimType.FACTUAL)
            c_status = getattr(c, "status", ClaimStatus.UNVERIFIABLE) if hasattr(c, "status") else c.get("status", ClaimStatus.UNVERIFIABLE)
            c_text = getattr(c, "text", "") if hasattr(c, "text") else c.get("text", "")

            if isinstance(c_type, str):
                c_type = ClaimType(c_type)
            if isinstance(c_status, str):
                c_status = ClaimStatus(c_status)

            if is_material and c_type == ClaimType.FACTUAL:
                if c_status in {ClaimStatus.CONTRADICTED, ClaimStatus.UNSUPPORTED}:
                    msg = f"Claim [{c_status.value}]: '{c_text}'"
                    unsupported_claims.append(msg)
                    blocking_failures.append(msg)

    passed = (len(blocking_failures) == 0) and (len(missing_criteria) == 0)
    all_reasons = blocking_failures if not passed else ["All blocking rubric criteria and claim grounding rules satisfied."]

    return ReleaseDecision(
        passed=passed,
        reasons=all_reasons,
        blocking_failures=blocking_failures,
        missing_criteria=missing_criteria,
        unsupported_claims=unsupported_claims,
    )
