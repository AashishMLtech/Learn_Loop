"""LangGraph Node Implementations Module.

Purpose:
    Defines the step functions (nodes) executed within the LangGraph state machine,
    handling input validation, generation, deterministic checking, LLM judging,
    release gating, targeted revision, and persistence.

Inputs/Outputs:
    Inputs: AgentState dictionary.
    Outputs: Partial state mutation dictionaries.

What it must NOT do:
    - Must NOT import UI or API transport components.
    - Must NOT proceed with LLM calls when cancel_requested is set.
    - Must NOT reuse stale evaluation results across versions.
"""
import logging
from typing import Any, Dict

from agent.state import AgentState
from evaluation.validators import load_rubric_dict, run_deterministic_checks
from guardrails.release_gate import release_decision
from memory.store import (
    EvaluationModel,
    LessonVersionModel,
    RejectionLogModel,
    RunModel,
    TokenUsageModel,
    get_db_context,
)
from shared.enums import CriterionStatus, EvidenceMode, RetryResult, RunStatus

logger = logging.getLogger("lesson_generator.nodes")


def check_is_cancelled(state: AgentState) -> bool:
    """Verifies whether the run has received a cancellation signal.

    Args:
        state: Current AgentState.

    Returns:
        True if cancellation was requested in state or database, False otherwise.
    """
    if state.get("cancel_requested"):
        return True
    run_id = state.get("run_id")
    if not run_id:
        return False
    try:
        with get_db_context() as db:
            run = db.get(RunModel, run_id)
            if run and run.cancel_requested:
                return True
    except Exception as exc:
        logger.warning("Could not check cancellation flag in DB: %s", exc)
    return False


def validate_input_node(state: AgentState) -> Dict[str, Any]:
    """Validates generation request inputs and sets defaults.

    Args:
        state: Input AgentState.

    Returns:
        State update dictionary.
    """
    run_id = state["run_id"]
    logger.info("Executing validate_input_node for run %s", run_id)

    max_retries = min(max(0, state.get("max_retries", 1)), 2)

    return {
        "max_retries": max_retries,
        "current_attempt": 1,
        "current_version_number": 1,
        "rejection_log": state.get("rejection_log", []),
        "status": RunStatus.RUNNING,
        "cancel_requested": check_is_cancelled(state),
    }


def generate_node(state: AgentState) -> Dict[str, Any]:
    """Executes the initial lesson generation call and stores Version 1.

    Args:
        state: Current AgentState.

    Returns:
        State update with generated Lesson and version identifier.
    """
    run_id = state["run_id"]
    if check_is_cancelled(state):
        logger.info("Run %s cancelled before generation.", run_id)
        return {"status": RunStatus.CANCELLED, "cancel_requested": True}

    logger.info("Executing generate_node for run %s", run_id)
    gen_service = state["services"]["generator_service"]
    token_tracker = state["token_tracker"]

    lesson = gen_service.generate(
        topic=state["topic"],
        learner_level=state["learner_level"].value,
        learning_objectives=state["learning_objectives"],
        target_length=state["target_length"].value,
        supplied_sources=state.get("supplied_sources", []),
        reference_context=state.get("reference_context", ""),
        pitfall_hints=state.get("pitfall_hints", ""),
        token_tracker=token_tracker,
        attempt=1,
    )

    with get_db_context() as db:
        v_record = LessonVersionModel(
            run_id=run_id,
            version_number=1,
            content=lesson.model_dump(),
            changes_made=[],
        )
        db.add(v_record)
        db.commit()
        db.refresh(v_record)
        version_id = v_record.id

        if token_tracker.records:
            latest = token_tracker.records[-1]
            t_record = TokenUsageModel(
                run_id=run_id,
                attempt=latest.attempt,
                call_type=latest.call_type.value,
                model=latest.model,
                prompt_tokens=latest.prompt_tokens,
                completion_tokens=latest.completion_tokens,
                total_tokens=latest.total_tokens,
                is_estimated=latest.is_estimated,
            )
            db.add(t_record)
            db.commit()

    return {
        "current_lesson": lesson,
        "current_changes_made": [],
        "current_version_id": version_id,
    }


def deterministic_checks_node(state: AgentState) -> Dict[str, Any]:
    """Re-runs all 7 zero-token deterministic rubric checks on the current version.

    Args:
        state: Current AgentState.

    Returns:
        State update with deterministic results, invalidating stale judge cache.
    """
    run_id = state["run_id"]
    lesson = state.get("current_lesson")
    if lesson is None:
        raise ValueError(f"Run {run_id} has no current_lesson to evaluate.")
    attempt = state.get("current_attempt", 1)
    logger.info("Executing deterministic_checks_node for run %s (attempt %d)", run_id, attempt)

    results = run_deterministic_checks(
        lesson=lesson,
        learner_level=state["learner_level"],
        target_length=state["target_length"],
        supplied_sources=state.get("supplied_sources", []),
    )

    failed = any(r.status != CriterionStatus.PASS for r in results)

    return {
        "deterministic_results": results,
        "deterministic_failed": failed,
        "judge_output": None,
        "all_criterion_results": results,
        "release_decision": None,
    }


def judge_node(state: AgentState) -> Dict[str, Any]:
    """Invokes the LLM judge only if deterministic checks pass.

    Args:
        state: Current AgentState.

    Returns:
        State update with JudgeOutput and aggregated results.
    """
    run_id = state["run_id"]
    if check_is_cancelled(state):
        logger.info("Run %s cancelled before judge.", run_id)
        return {"status": RunStatus.CANCELLED, "cancel_requested": True}

    attempt = state.get("current_attempt", 1)
    logger.info("Executing judge_node for run %s (attempt %d)", run_id, attempt)

    judge_service = state["services"]["judge_service"]
    token_tracker = state["token_tracker"]
    lesson = state["current_lesson"]

    judge_output = judge_service.judge(
        topic=state["topic"],
        learning_objectives=state["learning_objectives"],
        lesson=lesson,
        reference_evidence_context=state.get("reference_context", "No reference document provided."),
        evidence_hash=state.get("evidence_hash", "none"),
        token_tracker=token_tracker,
        attempt=attempt,
    )

    with get_db_context() as db:
        for rec in token_tracker.records:
            if rec.attempt == attempt and rec.call_type.value in {"judge", "repair"}:
                t_record = TokenUsageModel(
                    run_id=run_id,
                    attempt=rec.attempt,
                    call_type=rec.call_type.value,
                    model=rec.model,
                    prompt_tokens=rec.prompt_tokens,
                    completion_tokens=rec.completion_tokens,
                    total_tokens=rec.total_tokens,
                    is_estimated=rec.is_estimated,
                )
                db.add(t_record)
        db.commit()

    combined = list(state.get("deterministic_results", [])) + list(judge_output.criteria_results)

    return {
        "judge_output": judge_output,
        "all_criterion_results": combined,
    }


def release_gate_node(state: AgentState) -> Dict[str, Any]:
    """Evaluates the pure deterministic release gate and records the evaluation.

    Args:
        state: Current AgentState.

    Returns:
        State update with ReleaseDecision.
    """
    run_id = state["run_id"]
    version_id = state.get("current_version_id")
    criterion_results = state.get("all_criterion_results", [])
    judge_output = state.get("judge_output")
    claims = judge_output.claims if judge_output else []
    evidence_mode = state.get("evidence_mode", EvidenceMode.MODEL_KNOWLEDGE_ONLY)
    rubric = load_rubric_dict()

    logger.info("Executing release_gate_node for run %s (%d criteria)", run_id, len(criterion_results))
    decision = release_decision(
        criterion_results=criterion_results,
        claims=claims,
        evidence_mode=evidence_mode,
        rubric=rubric,
    )

    judge_model = state["services"]["judge_service"].model if "judge_service" in state.get("services", {}) else "judge"

    if version_id:
        with get_db_context() as db:
            eval_record = EvaluationModel(
                run_id=run_id,
                lesson_version_id=version_id,
                rubric_version="1.0.0",
                judge_model=judge_model,
                criterion_results=[cr.model_dump() for cr in criterion_results],
                claims=[c.model_dump() for c in claims],
                passed=decision.passed,
            )
            db.add(eval_record)
            db.commit()

    return {"release_decision": decision}


def prepare_revision_node(state: AgentState) -> Dict[str, Any]:
    """Extracts compact failure feedback and records the rejection log entry.

    Args:
        state: Current AgentState.

    Returns:
        State update with failed_criteria_feedback and updated rejection_log.
    """
    run_id = state["run_id"]
    attempt = state.get("current_attempt", 1)
    logger.info("Executing prepare_revision_node for run %s (attempt %d)", run_id, attempt)

    criterion_results = state.get("all_criterion_results", [])
    failed_items = [cr for cr in criterion_results if cr.status != CriterionStatus.PASS]

    failed_names = [f.criterion_id for f in failed_items]
    failed_reasons = [f.reason for f in failed_items]

    feedback_lines = []
    for item in failed_items:
        sec = f" [Section: {item.affected_section}]" if item.affected_section else ""
        fix = f" -> Fix: {item.suggested_fix}" if item.suggested_fix else ""
        feedback_lines.append(f"- Criterion '{item.criterion_id}' ({item.severity.value}){sec}: {item.reason}{fix}")

    feedback_text = "\n".join(feedback_lines) if feedback_lines else "Refine instructional clarity."

    log_entry = {
        "attempt": attempt,
        "failed_criteria": failed_names,
        "reasons": failed_reasons,
        "changes_made": state.get("current_changes_made", []),
        "result": RetryResult.RETRYING.value,
    }

    rejection_log = list(state.get("rejection_log", []))
    rejection_log.append(log_entry)

    with get_db_context() as db:
        r_entry = RejectionLogModel(
            run_id=run_id,
            attempt=attempt,
            failed_criteria=failed_names,
            reasons=failed_reasons,
            changes_made=state.get("current_changes_made", []),
            result=RetryResult.RETRYING.value,
        )
        db.add(r_entry)
        db.commit()

    return {
        "failed_criteria_feedback": feedback_text,
        "rejection_log": rejection_log,
    }


def revise_node(state: AgentState) -> Dict[str, Any]:
    """Generates an improved lesson draft and tracks changes made.

    Args:
        state: Current AgentState.

    Returns:
        State update with revised Lesson, new version ID, and changes list.
    """
    run_id = state["run_id"]
    if check_is_cancelled(state):
        logger.info("Run %s cancelled before revision.", run_id)
        return {"status": RunStatus.CANCELLED, "cancel_requested": True}

    new_attempt = state.get("current_attempt", 1) + 1
    new_version_num = state.get("current_version_number", 1) + 1
    logger.info("Executing revise_node for run %s (attempt %d, version %d)", run_id, new_attempt, new_version_num)

    gen_service = state["services"]["generator_service"]
    token_tracker = state["token_tracker"]
    prev_lesson = state["current_lesson"]
    feedback = state.get("failed_criteria_feedback", "Resolve all reported issues.")

    rev_out = gen_service.revise(
        topic=state["topic"],
        learner_level=state["learner_level"].value,
        learning_objectives=state["learning_objectives"],
        previous_lesson=prev_lesson,
        failure_feedback=feedback,
        token_tracker=token_tracker,
        attempt=new_attempt,
    )

    with get_db_context() as db:
        v_record = LessonVersionModel(
            run_id=run_id,
            version_number=new_version_num,
            content=rev_out.lesson.model_dump(),
            changes_made=rev_out.changes_made,
        )
        db.add(v_record)
        db.commit()
        db.refresh(v_record)
        version_id = v_record.id

        if token_tracker.records:
            latest = token_tracker.records[-1]
            t_record = TokenUsageModel(
                run_id=run_id,
                attempt=latest.attempt,
                call_type=latest.call_type.value,
                model=latest.model,
                prompt_tokens=latest.prompt_tokens,
                completion_tokens=latest.completion_tokens,
                total_tokens=latest.total_tokens,
                is_estimated=latest.is_estimated,
            )
            db.add(t_record)
            db.commit()

    return {
        "current_lesson": rev_out.lesson,
        "current_changes_made": rev_out.changes_made,
        "current_attempt": new_attempt,
        "current_version_number": new_version_num,
        "current_version_id": version_id,
    }


def persist_node(state: AgentState) -> Dict[str, Any]:
    """Finalizes successful run state and records terminal PASS.

    Args:
        state: Current AgentState.

    Returns:
        Terminal state update with status PASS.
    """
    run_id = state["run_id"]
    version_id = state.get("current_version_id")
    attempt = state.get("current_attempt", 1)
    logger.info("Executing persist_node for run %s: STATUS PASS", run_id)

    log_entry = {
        "attempt": attempt,
        "failed_criteria": [],
        "reasons": [],
        "changes_made": state.get("current_changes_made", []),
        "result": RetryResult.PASS.value,
    }
    rejection_log = list(state.get("rejection_log", []))
    rejection_log.append(log_entry)

    with get_db_context() as db:
        run = db.get(RunModel, run_id)
        if run:
            run.status = RunStatus.PASS.value
            run.final_lesson_id = version_id

        r_entry = RejectionLogModel(
            run_id=run_id,
            attempt=attempt,
            failed_criteria=[],
            reasons=[],
            changes_made=state.get("current_changes_made", []),
            result=RetryResult.PASS.value,
        )
        db.add(r_entry)
        db.commit()

    return {
        "status": RunStatus.PASS,
        "rejection_log": rejection_log,
    }


def persist_rejection_node(state: AgentState) -> Dict[str, Any]:
    """Finalizes rejected or cancelled run state and records terminal audit.

    Args:
        state: Current AgentState.

    Returns:
        Terminal state update with status REJECTED or CANCELLED.
    """
    run_id = state["run_id"]
    version_id = state.get("current_version_id")
    attempt = state.get("current_attempt", 1)
    status = state.get("status", RunStatus.REJECTED)

    if state.get("cancel_requested"):
        status = RunStatus.CANCELLED
    elif status == RunStatus.RUNNING:
        status = RunStatus.REJECTED

    logger.warning("Executing persist_rejection_node for run %s: STATUS %s", run_id, status.value)

    criterion_results = state.get("all_criterion_results", [])
    failed_items = [cr for cr in criterion_results if cr.status != CriterionStatus.PASS]
    failed_names = [f.criterion_id for f in failed_items]
    failed_reasons = [f.reason for f in failed_items]

    log_entry = {
        "attempt": attempt,
        "failed_criteria": failed_names,
        "reasons": failed_reasons,
        "changes_made": state.get("current_changes_made", []),
        "result": status.value,
    }
    rejection_log = list(state.get("rejection_log", []))
    rejection_log.append(log_entry)

    with get_db_context() as db:
        run = db.get(RunModel, run_id)
        if run:
            run.status = status.value
            run.final_lesson_id = version_id
            if not run.error_message:
                run.error_message = (
                    "Run cancelled by user request."
                    if status == RunStatus.CANCELLED
                    else "Retry cap exhausted without satisfying blocking rubric criteria."
                )

        r_entry = RejectionLogModel(
            run_id=run_id,
            attempt=attempt,
            failed_criteria=failed_names,
            reasons=failed_reasons,
            changes_made=state.get("current_changes_made", []),
            result=status.value,
        )
        db.add(r_entry)
        db.commit()

    return {
        "status": status,
        "rejection_log": rejection_log,
    }
