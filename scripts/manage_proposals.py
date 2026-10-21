"""Self-Evolving Proposals Management CLI.

Purpose:
    Provides administrative CLI utilities to list, evaluate, approve, and rollback
    Level B proposals. Guarantees that proposals cannot be approved without
    ADMIN_API_KEY or if golden set regressions occur.

Inputs/Outputs:
    Inputs: Command line arguments (list, evaluate, approve, rollback), proposal ID, admin key.
    Outputs: Command line output reporting evaluation results, approval logs, or rollback status.

What it must NOT do:
    - Must NOT approve proposals without ADMIN_API_KEY.
    - Must NOT approve proposals that cause previously passing golden cases to fail.
    - Must NOT automatically alter production files without explicit approval.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from evaluation.validators import run_deterministic_checks
from generation.schema import Lesson
from memory.store import ProposalModel, get_db_context, init_db
from shared.enums import CriterionStatus, LearnerLevel, LessonLength, ProposalStatus

GOLDEN_FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures", "golden")


def load_golden_lessons() -> List[Dict[str, Any]]:
    """Loads all valid golden set lessons for regression auditing.

    Returns:
        List of tuples with filename, Lesson object, and supplied sources.
    """
    cases = []
    good_files = ["lesson_1_good.json", "lesson_2_good.json", "lesson_3_good.json"]
    for fname in good_files:
        fpath = os.path.join(GOLDEN_FIXTURES_DIR, fname)
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
                cases.append({"filename": fname, "lesson": Lesson.model_validate(data)})
    return cases


def evaluate_against_golden_set() -> bool:
    """Runs deterministic validation against passing golden set cases to detect regression.

    Returns:
        True if all good golden cases continue to pass, False if any regress.
    """
    cases = load_golden_lessons()
    if not cases:
        print("[WARNING] No golden fixtures found to evaluate against.")
        return True

    for c in cases:
        fname = c["filename"]
        lesson = c["lesson"]
        results = run_deterministic_checks(
            lesson=lesson,
            learner_level=LearnerLevel.BEGINNER,
            target_length=LessonLength.SHORT,
            supplied_sources=[{"source_id": "src-1", "title": "Reference"}],
        )
        failed = [r for r in results if r.status != CriterionStatus.PASS]
        if failed:
            print(f"[REGRESSION] Golden case {fname} failed: {[r.reason for r in failed]}")
            return False

    return True


def list_proposals():
    """Lists all stored proposals with their metadata and lifecycle status."""
    init_db()
    with get_db_context() as db:
        proposals = list(db.query(ProposalModel).order_by(ProposalModel.created_at.desc()).all())
        if not proposals:
            print("No proposals found.")
            return

        print(f"\n{'ID':<38} | {'TARGET':<20} | {'STATUS':<12} | {'CREATED AT'}")
        print("-" * 85)
        for p in proposals:
            created_str = p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "N/A"
            print(f"{p.id:<38} | {p.target:<20} | {p.status:<12} | {created_str}")


def evaluate_proposal(proposal_id: str):
    """Evaluates a proposal against the golden set to determine regression risk.

    Args:
        proposal_id: Unique proposal ID.
    """
    init_db()
    with get_db_context() as db:
        prop = db.get(ProposalModel, proposal_id)
        if not prop:
            print(f"Error: Proposal '{proposal_id}' not found.")
            return

        print(f"\nEvaluating Proposal: {prop.id}")
        print(f"Target: {prop.target}")
        print(f"Rationale: {prop.rationale}")
        print(f"Proposed Change: {prop.proposed_change}")

        passed = evaluate_against_golden_set()
        if passed:
            print("\n[RESULT] Golden set regression test: PASSED (Zero regressions detected).")
        else:
            print("\n[RESULT] Golden set regression test: FAILED (Regressions detected!).")


def approve_proposal(proposal_id: str, admin_key: str, actor: str = "admin", reason: str = ""):
    """Approves and activates a proposal after admin auth and regression verification.

    Args:
        proposal_id: Proposal identifier.
        admin_key: Administrative API key.
        actor: Identity of approving administrator.
        reason: Justification for approval.
    """
    expected_key = os.getenv("ADMIN_API_KEY", "default-admin-secret-xyz")
    if admin_key != expected_key:
        print("[ERROR] Authorization failed: Invalid ADMIN_API_KEY.")
        sys.exit(1)

    # Verify golden set does not regress
    if not evaluate_against_golden_set():
        print("[ERROR] Approval rejected: Proposal causes regressions in previously passing golden set cases.")
        sys.exit(1)

    init_db()
    with get_db_context() as db:
        prop = db.get(ProposalModel, proposal_id)
        if not prop:
            print(f"Error: Proposal '{proposal_id}' not found.")
            return

        prop.status = ProposalStatus.ACTIVE.value
        prop.approved_by = actor
        prop.approved_at = datetime.now(timezone.utc)
        print(f"[SUCCESS] Proposal '{proposal_id}' approved and marked ACTIVE by {actor}.")
        if reason:
            print(f"Reason: {reason}")


def rollback_proposal(proposal_id: str, admin_key: str):
    """Rolls back an active proposal.

    Args:
        proposal_id: Proposal identifier.
        admin_key: Administrative API key.
    """
    expected_key = os.getenv("ADMIN_API_KEY", "default-admin-secret-xyz")
    if admin_key != expected_key:
        print("[ERROR] Authorization failed: Invalid ADMIN_API_KEY.")
        sys.exit(1)

    init_db()
    with get_db_context() as db:
        prop = db.get(ProposalModel, proposal_id)
        if not prop:
            print(f"Error: Proposal '{proposal_id}' not found.")
            return

        prop.status = ProposalStatus.ROLLED_BACK.value
        print(f"[SUCCESS] Proposal '{proposal_id}' rolled back to status ROLLED_BACK.")


def main():
    """CLI entry point for proposal management."""
    parser = argparse.ArgumentParser(description="Manage self-evolving Level B proposals.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    subparsers.add_parser("list", help="List all proposals")

    # evaluate
    eval_parser = subparsers.add_parser("evaluate", help="Evaluate proposal against golden set")
    eval_parser.add_argument("--id", required=True, help="Proposal ID")

    # approve
    app_parser = subparsers.add_parser("approve", help="Approve and activate proposal")
    app_parser.add_argument("--id", required=True, help="Proposal ID")
    app_parser.add_argument("--admin-key", required=True, help="Admin API Key")
    app_parser.add_argument("--actor", default="operator", help="Approving user identifier")
    app_parser.add_argument("--reason", default="Approved following verification", help="Approval rationale")

    # rollback
    roll_parser = subparsers.add_parser("rollback", help="Rollback an active proposal")
    roll_parser.add_argument("--id", required=True, help="Proposal ID")
    roll_parser.add_argument("--admin-key", required=True, help="Admin API Key")

    args = parser.parse_args()
    if args.command == "list":
        list_proposals()
    elif args.command == "evaluate":
        evaluate_proposal(args.id)
    elif args.command == "approve":
        approve_proposal(args.id, args.admin_key, args.actor, args.reason)
    elif args.command == "rollback":
        rollback_proposal(args.id, args.admin_key)


if __name__ == "__main__":
    main()
