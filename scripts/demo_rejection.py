"""Demonstration Script for Autonomous Rejection and Retry Feedback Loop.

Purpose:
    Demonstrates the evaluation and rejection workflow on the command line.
    When executed with --seed-flaw, injects an intentional defect, executes
    deterministic validation, logs the rejection details to stdout,
    and exits with code 0 to signify successful demonstration of the rejection gate.

Inputs/Outputs:
    Inputs: Command line flags (--seed-flaw [jargon|code|citation]).
    Outputs: Formatted rejection audit log printed to stdout; exit code 0.

What it must NOT do:
    - Must NOT exit non-zero when successfully demonstrating rejection under --seed-flaw.
    - Must NOT bypass rubric evaluation rules.
"""
import argparse
import json
import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from evaluation.validators import run_deterministic_checks
from generation.schema import Lesson
from shared.enums import CriterionStatus, LearnerLevel, LessonLength, RetryResult

GOLDEN_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "golden"


def load_fixture_lesson(filename: str) -> Lesson:
    """Loads a golden lesson fixture from disk.

    Args:
        filename: Fixture file name.

    Returns:
        Validated Lesson instance.
    """
    fpath = GOLDEN_DIR / filename
    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Lesson.model_validate(data)


def run_demo(seed_flaw: str) -> int:
    """Executes the rejection demonstration workflow.

    Args:
        seed_flaw: Flaw category to demonstrate ('jargon', 'code', 'citation', or 'none').

    Returns:
        Process exit code (0 for expected behavior).
    """
    flaw_map = {
        "jargon": "lesson_4_flawed_jargon.json",
        "code": "lesson_5_flawed_code.json",
        "citation": "lesson_6_flawed_citations.json",
        "none": "lesson_1_good.json",
    }

    target_file = flaw_map.get(seed_flaw, "lesson_4_flawed_jargon.json")
    print("\n=======================================================")
    print("  Autonomous Rejection & Self-Correction Demonstration")
    print("=======================================================")
    print(f"Target Fixture: {target_file}")
    print(f"Seeded Flaw Category: {seed_flaw.upper()}")

    lesson = load_fixture_lesson(target_file)
    supplied_sources = [{"source_id": "src-1", "title": "Reference Material"}]

    print(f"Lesson Title: '{lesson.title}'")
    print("Evaluating against 13-criterion rubric (Deterministic Phase)...")

    results = run_deterministic_checks(
        lesson=lesson,
        learner_level=LearnerLevel.BEGINNER,
        target_length=LessonLength.SHORT,
        supplied_sources=supplied_sources,
    )

    failed_criteria = [r for r in results if r.status != CriterionStatus.PASS]

    if failed_criteria:
        print("\n[EVALUATION RESULT: REJECTED] - Blocking criteria failed!")
        print(f"{'-' * 55}")
        print("Attempt: 1")
        print(f"Result: {RetryResult.REJECTED.value}")
        print(f"Failed Criteria ({len(failed_criteria)}):")
        for fc in failed_criteria:
            print(f"  • [{fc.severity.upper()}] {fc.criterion_id}: {fc.reason}")
            if fc.suggested_fix:
                print(f"    Suggested Fix: {fc.suggested_fix}")

        print("\n[RETRY DISPATCH]: Formulating targeted revision instructions...")
        changes_to_make = [
            f"Fix {fc.criterion_id} by addressing: {fc.reason}" for fc in failed_criteria
        ]
        print(f"Changes queued for Attempt 2: {changes_to_make}")
        print("\n[SUCCESS]: Rejection demonstration executed as expected.")
        # Exits 0 on rejection when demonstrating failure per specification
        return 0
    else:
        print("\n[EVALUATION RESULT: PASS] - All criteria met!")
        print("Lesson approved for publication without revisions.")
        return 0


def main() -> None:
    """CLI entry point for rejection demonstration."""
    parser = argparse.ArgumentParser(description="Demonstrate autonomous lesson evaluation rejection.")
    parser.add_argument(
        "--seed-flaw",
        choices=["jargon", "code", "citation", "none"],
        default="jargon",
        help="Type of flaw to inject/demonstrate (default: jargon)",
    )
    args = parser.parse_args()
    code = run_demo(args.seed_flaw)
    sys.exit(code)


if __name__ in {"__main__", "__mp_main__"}:
    main()
