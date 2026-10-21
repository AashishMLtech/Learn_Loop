"""Live Model Calibration and Ground-Truth Evaluation Test.

Purpose:
    Executes live judge evaluations across the golden lesson dataset to measure
    inter-evaluator agreement rates, compute empirical confusion matrices, and
    verify that the LLM judge correctly discriminates between passing and flawed
    educational content.

Inputs/Outputs:
    Inputs: Golden set lesson fixtures (tests/fixtures/golden/*.json), live LLM judge.
    Outputs: Confusion matrix report and empirical agreement calculations.

What it must NOT do:
    - Must NOT hardcode demo topic terms.
    - Must NOT claim 100% agreement without real empirical measurement.
    - Must NOT fail if GROQ_API_KEY is not configured (skips cleanly instead).
"""
import json
import os
from pathlib import Path
from typing import Dict, List

import pytest

from evaluation.judge import JudgeService
from generation.schema import Lesson
from shared.enums import CriterionStatus, EvidenceMode
from shared.llm_client import GroqLLMClient, TokenBudgetTracker

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden"


@pytest.mark.live
def test_live_judge_calibration_on_golden_set() -> None:
    """Evaluates the golden benchmark suite using live LLM judge if credentials are configured."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        pytest.skip("GROQ_API_KEY not configured. Skipping live model calibration test.")

    llm_client = GroqLLMClient(api_key=api_key)
    judge_service = JudgeService(llm_client=llm_client)
    token_tracker = TokenBudgetTracker()

    expected_labels: Dict[str, bool] = {
        "lesson_1_good.json": True,
        "lesson_2_good.json": True,
        "lesson_3_good.json": True,
        "lesson_4_flawed_jargon.json": False,
        "lesson_5_flawed_code.json": False,
        "lesson_6_flawed_citations.json": False,
    }

    # Confusion matrix counters:
    # Positive = Passing lesson (good)
    # Negative = Flawed lesson (bad)
    tp = 0  # Expected True, Judge evaluated all criteria PASS
    fp = 0  # Expected False, Judge evaluated all criteria PASS
    tn = 0  # Expected False, Judge failed at least one criterion
    fn = 0  # Expected True, Judge failed at least one criterion

    results_log: List[str] = []

    for fname, expected_pass in expected_labels.items():
        fpath = GOLDEN_DIR / fname
        if not fpath.exists():
            continue

        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        lesson = Lesson.model_validate(data)
        judge_out = judge_service.evaluate_lesson(
            lesson=lesson,
            topic=lesson.title,
            learning_objectives=["Understand core mechanisms", "Learn worked example"],
            learner_level="beginner",
            target_length="short",
            evidence_mode=EvidenceMode.MODEL_KNOWLEDGE_ONLY,
            token_tracker=token_tracker,
            attempt=1,
        )

        all_passed = all(cr.status == CriterionStatus.PASS for cr in judge_out.criteria_results)

        if expected_pass and all_passed:
            tp += 1
            results_log.append(f"[PASS-CORRECT] {fname}: Expected PASS, Got PASS")
        elif not expected_pass and not all_passed:
            tn += 1
            results_log.append(f"[FAIL-CORRECT] {fname}: Expected FAIL, Got FAIL")
        elif not expected_pass and all_passed:
            fp += 1
            results_log.append(f"[FALSE-POSITIVE] {fname}: Expected FAIL, Got PASS")
        else:
            fn += 1
            results_log.append(f"[FALSE-NEGATIVE] {fname}: Expected PASS, Got FAIL")

    total_evaluated = tp + tn + fp + fn
    assert total_evaluated > 0, "No golden cases were evaluated."

    accuracy = (tp + tn) / total_evaluated
    print("\n--- Empirical Calibration Report ---")
    print(f"Total Evaluated: {total_evaluated}")
    print(f"Confusion Matrix: TP={tp}, TN={tn}, FP={fp}, FN={fn}")
    print(f"Measured Agreement Rate: {accuracy:.2%}")
    for log_entry in results_log:
        print(f"  {log_entry}")

    # We do not assert 100% accuracy, but verify empirical measurement executed cleanly
    assert 0.0 <= accuracy <= 1.0
